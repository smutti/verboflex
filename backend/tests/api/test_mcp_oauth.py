"""OAuth wire flows against migrated PostgreSQL and real Streamable HTTP MCP."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from verboflex.auth.rate_limits import get_redis_client
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.models.mcp_oauth import McpAuthorizationRequest, McpClient, McpGrant, McpToken
from verboflex.models.user import User
from verboflex.services import mcp_oauth as oauth

spec = importlib.util.spec_from_file_location(
    "mcp_review_support", Path(__file__).with_name("test_translation_reviews.py")
)
assert spec and spec.loader
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
RESOURCE = "http://localhost:8080/mcp"
CALLBACK = "http://127.0.0.1:19342/callback"
VERIFIER = "a" * 64
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
)


class Redis:
    def eval(self, *args):
        return [1, 60]


@pytest.fixture(scope="module")
def database():
    with support._review_database() as factory:
        yield factory


@pytest.fixture
def env(database, monkeypatch):
    import verboflex.main as main
    import verboflex.mcp_http as transport

    settings = support.SUPPORT._settings().model_copy(update={"mcp_public_url": RESOURCE})
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(transport, "SessionFactory", database)
    application = main.create_app()

    def session():
        with database() as db:
            yield db

    application.dependency_overrides[get_db_session] = session
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_redis_client] = Redis
    jwt = support.SUPPORT._create_authority(database, role_names=("admin",))
    with TestClient(application, base_url="http://localhost:8080") as client:
        yield client, {"Authorization": f"Bearer {jwt}"}, database, settings


def register(client, **extra):
    response = client.post(
        "/oauth/register", json={"client_name": "Test MCP", "redirect_uris": [CALLBACK], **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


def authorize(client, registered, **extra):
    parameters = dict(
        client_id=registered["client_id"],
        redirect_uri=CALLBACK,
        response_type="code",
        resource=RESOURCE,
        code_challenge=CHALLENGE,
        code_challenge_method="S256",
        state="opaque state & data",
        scope="verboflex:read verboflex:write",
    )
    parameters.update(extra)
    response = client.get("/oauth/authorize", params=parameters, follow_redirects=False)
    return response


def approve(env, *, write=False, registered=None, headers=None):
    client, owner, _, _ = env
    registered = registered or register(client)
    response = authorize(client, registered)
    assert response.status_code == 302, response.text
    request_id = parse_qs(urlsplit(response.headers["location"]).query)["request"][0]
    path = "/api/v1/mcp/authorization/" + request_id
    assert client.get(path, headers=owner).status_code == 200
    decision = client.post(
        path, headers=headers or owner, json={"allow": True, "allow_write": write}
    )
    assert decision.status_code == 200, decision.text
    query = parse_qs(urlsplit(decision.json()["redirect_url"]).query)
    assert query["state"] == ["opaque state & data"]
    assert client.post(path, headers=owner, json={"allow": True}).status_code == 404
    return registered, dict(
        grant_type="authorization_code",
        client_id=registered["client_id"],
        code=query["code"][0],
        redirect_uri=CALLBACK,
        code_verifier=VERIFIER,
        resource=RESOURCE,
    )


def issue(env, **kwargs):
    registered, data = approve(env, **kwargs)
    response = env[0].post("/oauth/token", data=data)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return registered, response.json(), data


def rpc(client, token, method, params=None, **headers):
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-06-18",
            **headers,
        },
    )


def test_discovery_and_read_only_http_tools(env):
    client, owner, factory, settings = env
    challenge = client.post("/mcp")
    assert challenge.status_code == 401
    assert "oauth-protected-resource" in challenge.headers["www-authenticate"]
    assert client.get("/.well-known/oauth-protected-resource/mcp").json()["resource"] == RESOURCE
    assert client.get("/.well-known/oauth-authorization-server").json()[
        "code_challenge_methods_supported"
    ] == ["S256"]
    _, tokens, data = issue(env)
    access = tokens["access_token"]
    assert tokens["scope"] == "verboflex:read"
    initialized = rpc(
        client,
        access,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    )
    assert initialized.status_code == 200, initialized.text
    result = rpc(client, access, "tools/list")
    assert result.status_code == 200, result.text
    tools = result.json()["result"]["tools"]
    assert len(tools) > 10 and all(item["annotations"]["readOnlyHint"] for item in tools)
    called = rpc(client, access, "tools/call", {"name": "list_projects_and_languages"})
    assert called.json()["result"]["structuredContent"]["status_code"] == 200, called.text
    denied = rpc(
        client,
        access,
        "tools/call",
        {"name": "create_project", "arguments": {"payload": {"name": "forbidden"}}},
    )
    assert denied.json()["result"]["isError"]
    assert (
        client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {access}"}).status_code
        == 401
    )
    assert rpc(client, owner["Authorization"][7:], "tools/list").status_code == 401
    assert (
        client.get("/api/v1/users/me", headers={"verboflex.mcp_principal": "admin"}).status_code
        == 401
    )
    assert rpc(client, access, "tools/list", Origin="https://evil.example").status_code == 403
    with factory() as session:
        assert session.get(McpToken, access) is None
        assert session.get(McpToken, oauth.digest(access)) is not None
        assert (
            session.scalar(
                select(McpAuthorizationRequest).where(
                    McpAuthorizationRequest.code_hash == data["code"]
                )
            )
            is None
        )
        oauth.load_authority(session, access, settings)


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("redirect_uri", CALLBACK + "/evil"),
        ("resource", "https://evil.example/mcp"),
        ("code_challenge_method", "plain"),
        ("scope", "admin"),
        ("code_challenge", "short"),
    ],
)
def test_authorization_rejects_untrusted_parameters(env, parameter, value):
    client = env[0]
    response = authorize(client, register(client), **{parameter: value})
    assert response.status_code == 400 and "location" not in response.headers


def test_consent_required_denial_and_owner_scoped_revocation(env):
    client, owner, factory, _ = env
    registered = register(client)
    response = authorize(client, registered)
    request_id = parse_qs(urlsplit(response.headers["location"]).query)["request"][0]
    path = "/api/v1/mcp/authorization/" + request_id
    assert client.post(path, json={"allow": True}).status_code == 401
    denied = client.post(path, headers=owner, json={"allow": False})
    assert parse_qs(urlsplit(denied.json()["redirect_url"]).query)["error"] == ["access_denied"]
    _, tokens, _ = issue(env, write=True)
    listed = client.get("/api/v1/mcp/connections", headers=owner).json()["items"]
    assert len(listed) == 1 and "verboflex:write" in listed[0]["scopes"]
    another = support.SUPPORT._create_authority(factory, role_names=("admin",))
    assert (
        client.delete(
            "/api/v1/mcp/connections/" + listed[0]["id"],
            headers={"Authorization": f"Bearer {another}"},
        ).status_code
        == 404
    )
    assert (
        client.delete("/api/v1/mcp/connections/" + listed[0]["id"], headers=owner).status_code
        == 204
    )
    assert rpc(client, tokens["access_token"], "tools/list").status_code == 401


@pytest.mark.parametrize(
    "field,value",
    [
        ("code_verifier", "b" * 64),
        ("resource", "http://localhost:8080/elsewhere"),
        ("redirect_uri", CALLBACK + "/elsewhere"),
    ],
)
def test_code_binding_and_replay(env, field, value):
    client = env[0]
    _, data = approve(env)
    bad = client.post("/oauth/token", data={**data, field: value})
    assert bad.status_code == 400
    success = client.post("/oauth/token", data=data)
    assert success.status_code == 200, success.text
    assert client.post("/oauth/token", data=data).status_code == 400
    assert rpc(client, success.json()["access_token"], "tools/list").status_code == 401


def test_refresh_rotation_reuse_and_token_version(env):
    client, _, factory, settings = env
    registered, tokens, _ = issue(env)
    data = dict(
        grant_type="refresh_token",
        client_id=registered["client_id"],
        refresh_token=tokens["refresh_token"],
        resource=RESOURCE,
    )
    rotated = client.post("/oauth/token", data=data)
    assert rotated.status_code == 200 and rotated.json()["refresh_token"] != tokens["refresh_token"]
    assert client.post("/oauth/token", data=data).status_code == 400
    assert rpc(client, rotated.json()["access_token"], "tools/list").status_code == 401
    _, fresh, _ = issue(env)
    with factory.begin() as session:
        authority = oauth.load_authority(session, fresh["access_token"], settings)
        session.get_one(User, authority.principal.user_id).token_version += 1
    assert rpc(client, fresh["access_token"], "tools/list").status_code == 401


def test_current_roles_enforced_even_with_write_scope(env):
    client, _, factory, _ = env
    viewer = support.SUPPORT._create_authority(factory, role_names=("viewer",))
    _, tokens, _ = issue(env, write=True, headers={"Authorization": f"Bearer {viewer}"})
    tools = rpc(client, tokens["access_token"], "tools/list").json()["result"]["tools"]
    assert len(tools) == 70
    denied = rpc(client, tokens["access_token"], "tools/call", {"name": "list_admin_projects"})
    assert denied.json()["result"]["structuredContent"]["status_code"] == 403, denied.text


def test_simultaneous_code_exchange_and_refresh_fail_closed(env):
    client, _, factory, settings = env
    registered, data = approve(env)

    def exchange(_):
        with factory() as session:
            try:
                return oauth.exchange_code(
                    session, session.get_one(McpClient, registered["client_id"]), data, settings
                )
            except oauth.OAuthError:
                return None

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(exchange, range(2)))
    assert sum(item is not None for item in outcomes) == 1
    successful = next(item for item in outcomes if item)
    assert rpc(client, successful["access_token"], "tools/list").status_code == 401
    registered, tokens, _ = issue(env)

    def refresh(_):
        with factory() as session:
            try:
                return oauth.rotate_token(
                    session,
                    session.get_one(McpClient, registered["client_id"]),
                    {"refresh_token": tokens["refresh_token"], "resource": RESOURCE},
                    settings,
                )
            except oauth.OAuthError:
                return None

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(refresh, range(2)))
    assert sum(item is not None for item in outcomes) == 1
    assert (
        rpc(
            client, next(item for item in outcomes if item)["access_token"], "tools/list"
        ).status_code
        == 401
    )


def test_confidential_client_auth_and_cleanup(env):
    client, _, factory, settings = env
    registered = register(client, token_endpoint_auth_method="client_secret_basic")
    registered, data = approve(env, registered=registered)
    assert client.post("/oauth/token", data=data).status_code == 401
    data.pop("client_id")
    response = client.post(
        "/oauth/token", data=data, auth=(registered["client_id"], registered["client_secret"])
    )
    assert response.status_code == 200, response.text
    with factory() as session:
        assert (
            session.get_one(McpClient, registered["client_id"]).secret_hash
            != registered["client_secret"]
        )
        authority = oauth.load_authority(session, response.json()["access_token"], settings)
        grant_id = authority.grant.id
        authority.grant.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        assert oauth.cleanup_oauth(session, datetime.now(UTC)) >= 1
        session.expire_all()
        assert session.get(McpGrant, grant_id) is None
        assert session.get(McpToken, oauth.digest(response.json()["refresh_token"])) is None


@pytest.mark.parametrize(
    "url",
    [
        "http://remote.example/mcp",
        "https://user:pass@example.com/mcp",
        "https://example.com/mcp?x=1",
        "https://example.com/elsewhere",
    ],
)
def test_resource_configuration_requires_safe_canonical_url(url):
    with pytest.raises(ValidationError):
        Settings(mcp_public_url=url)


def test_expiry_revocation_and_anonymous_limits(env):
    client, _, factory, settings = env
    registered, tokens, _ = issue(env)
    with factory.begin() as session:
        session.get_one(McpToken, oauth.digest(tokens["access_token"])).expires_at = datetime.now(
            UTC
        ) - timedelta(seconds=1)
    assert rpc(client, tokens["access_token"], "tools/list").status_code == 401
    refreshed = client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": registered["client_id"],
            "refresh_token": tokens["refresh_token"],
            "resource": RESOURCE,
        },
    )
    assert refreshed.status_code == 200
    assert (
        client.post(
            "/oauth/revoke",
            data={"client_id": registered["client_id"], "token": refreshed.json()["refresh_token"]},
        ).status_code
        == 200
    )
    assert rpc(client, refreshed.json()["access_token"], "tools/list").status_code == 401
    assert (
        client.post(
            "/oauth/revoke", data={"client_id": registered["client_id"], "token": "unknown"}
        ).status_code
        == 200
    )

    class ExhaustedRedis:
        def eval(self, *args):
            return [1000, 60]

    client.app.dependency_overrides[get_redis_client] = ExhaustedRedis
    assert client.post("/oauth/register", json={"redirect_uris": [CALLBACK]}).status_code == 429

    class OfflineRedis:
        def eval(self, *args):
            from redis.exceptions import ConnectionError

            raise ConnectionError("private location")

    client.app.dependency_overrides[get_redis_client] = OfflineRedis
    response = client.post("/oauth/token", data={"client_id": registered["client_id"]})
    assert response.status_code == 503 and "private" not in response.text


def test_registration_bounds_and_client_binding(env):
    client = env[0]
    for redirect in [
        "http://example.com/callback",
        "https://example.com/#fragment",
        "file:///tmp/callback",
    ]:
        assert client.post("/oauth/register", json={"redirect_uris": [redirect]}).status_code == 400
    assert client.post("/oauth/register", content="x" * 17000).status_code == 413
    first, data = approve(env)
    second = register(client)
    assert (
        client.post("/oauth/token", data={**data, "client_id": second["client_id"]}).status_code
        == 400
    )
    valid = client.post("/oauth/token", data=data)
    assert valid.status_code == 200
    assert (
        client.post(
            "/oauth/token",
            data={
                "client_id": second["client_id"],
                "grant_type": "refresh_token",
                "refresh_token": valid.json()["refresh_token"],
            },
        ).status_code
        == 400
    )


def test_http_write_uses_existing_api_permissions_and_persistence(env):
    client, _, _, _ = env
    _, tokens, _ = issue(env, write=True)
    result = rpc(
        client,
        tokens["access_token"],
        "tools/call",
        {
            "name": "create_project",
            "arguments": {"payload": {"name": "MCP isolated project"}},
        },
    )
    payload = result.json()["result"]
    assert not payload["isError"], result.text
    assert payload["structuredContent"]["status_code"] == 201
    project_id = payload["structuredContent"]["data"]["id"]
    read_back = rpc(
        client,
        tokens["access_token"],
        "tools/call",
        {
            "name": "get_project",
            "arguments": {"product_id": project_id},
        },
    )
    assert read_back.json()["result"]["structuredContent"]["data"]["id"] == project_id
