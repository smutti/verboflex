"""Protocol and security contracts against an observable REST boundary."""

from __future__ import annotations

import asyncio
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from jsonschema import Draft202012Validator
from mcp import Client

from verboflex_mcp.api import ApiClient
from verboflex_mcp.catalog import OPERATIONS
from verboflex_mcp.server import create_server, load_contract
from verboflex_mcp.session import COOKIE, ConnectorError, Session, SessionStore, api_url


@pytest.fixture
def store(tmp_path):
    session = SessionStore(tmp_path / "session.json")
    session.prepare()
    session.write(
        Session(
            "https://api.example.test/api/v1", "access-secret", "refresh-secret", time.time() + 900
        )
    )
    return session


def call(store, handler, name, arguments=None, *, read_only=False):
    async def run():
        with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False) as http:
            async with Client(create_server(ApiClient(store, http), read_only=read_only)) as client:
                return await client.call_tool(name, arguments or {})

    return asyncio.run(run())


def test_catalog_is_closed_valid_and_annotated(store):
    async def run():
        with httpx.Client() as http:
            async with Client(create_server(ApiClient(store, http))) as client:
                tools = (await client.list_tools()).tools
                assert len(tools) == len(OPERATIONS) == 70
                for tool in tools:
                    Draft202012Validator.check_schema(tool.input_schema)
                    assert tool.annotations.open_world_hint
                    assert (
                        tool.annotations.read_only_hint == (load_contract()[tool.name]["read_only"])
                    )
                assert not {"login", "request", "sql", "reset_password"} & {t.name for t in tools}

    asyncio.run(run())


def test_cursor_and_repeated_language_parameters_pass_through_without_autopaging(store):
    seen = []

    def handler(request):
        seen.append(request)
        assert request.headers["Authorization"] == "Bearer access-secret"
        assert request.url.path == "/api/v1/translations/keys"
        assert request.url.params.get_list("visible_languages") == ["it", "en"]
        return httpx.Response(200, json={"items": [], "next_cursor": "cursor-next"})

    response = call(store, handler, "search_translation_keys", {"visible_languages": ["it", "en"]})
    assert not response.is_error
    assert response.structured_content["data"]["next_cursor"] == "cursor-next"
    assert len(seen) == 1


@pytest.mark.parametrize("status", [401, 403, 409, 422, 429, 503])
def test_api_errors_are_mcp_errors_and_writes_are_never_retried(store, status):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(status, json={"detail": "conflict", "latest": {"version": 2}})

    response = call(
        store,
        handler,
        "review_translation",
        {
            "translation_group_id": "00000000-0000-4000-8000-000000000001",
            "payload": {"target_state": "approved", "expected_version": 1},
        },
    )
    assert response.is_error
    assert response.structured_content["status_code"] == status
    assert len(seen) == 1
    if status == 409:
        assert response.structured_content["data"]["latest"]["version"] == 2


def test_delete_body_is_preserved(store):
    def handler(request):
        assert request.method == "DELETE"
        assert json.loads(request.content) == {"expected_version": 7}
        return httpx.Response(204)

    response = call(
        store,
        handler,
        "remove_translation_limit",
        {
            "translation_group_id": "00000000-0000-4000-8000-000000000001",
            "language": "it",
            "payload": {"expected_version": 7},
        },
    )
    assert not response.is_error
    assert response.structured_content["data"] is None


def test_read_only_hides_and_rejects_mutations(store):
    async def run():
        with httpx.Client() as http:
            async with Client(create_server(ApiClient(store, http), read_only=True)) as client:
                tools = (await client.list_tools()).tools
                assert "whoami" in {t.name for t in tools}
                assert "save_translation" not in {t.name for t in tools}
                denied = await client.call_tool("save_translation", {})
                assert denied.is_error

    asyncio.run(run())


@pytest.mark.parametrize(
    "arguments",
    [
        {"translation_group_id": "../../auth/token"},
        {
            "translation_group_id": "00000000-0000-4000-8000-000000000001",
            "url": "https://evil.test",
        },
        {},
    ],
)
def test_invalid_or_extra_arguments_never_reach_api(store, arguments):
    def handler(request):
        pytest.fail("Invalid arguments reached API")

    assert call(store, handler, "get_translation", arguments).is_error


@pytest.mark.parametrize("kind", ["timeout", "redirect", "oversize", "html", "unexpected"])
def test_safe_bounded_errors_and_no_redirect_or_retry(store, kind):
    seen = []

    def handler(request):
        seen.append(request)
        if kind == "timeout":
            raise httpx.ReadTimeout("secret-in-exception", request=request)
        if kind == "unexpected":
            raise RuntimeError("secret-in-exception")
        if kind == "redirect":
            return httpx.Response(307, headers={"Location": "https://evil.test"})
        if kind == "oversize":
            return httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1))
        return httpx.Response(200, text="<html>secret-in-exception</html>")

    response = call(store, handler, "whoami")
    assert response.is_error
    assert "secret-in-exception" not in str(response)
    assert "access-secret" not in str(response)
    assert len(seen) == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/api/v1",
        "https://user:secret@example.com/api/v1",
        "https://example.com/api/v1?token=secret",
        "file:///tmp/x",
        "https://example.com/#part",
        "https://[broken/api/v1",
        "https://example.com:bad/api/v1",
    ],
)
def test_reject_unsafe_api_origins(url):
    with pytest.raises(ConnectorError):
        api_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/api/v1/",
        "http://127.0.0.1:8000/api/v1",
        "http://[::1]:8000/api/v1",
        "https://example.com/api/v1",
    ],
)
def test_accept_remote_tls_and_loopback(url):
    assert api_url(url) == url.rstrip("/")


def test_login_private_storage_and_logout_revocation(tmp_path):
    store = SessionStore(tmp_path / "session.json")

    def handler(request):
        if request.url.path.endswith("/token"):
            assert "password=password-secret" in request.content.decode()
            return httpx.Response(
                200,
                json={"access_token": "access-secret", "expires_in": 900},
                headers={"Set-Cookie": f"{COOKIE}=refresh-secret; Secure; Path=/"},
            )
        assert request.url.path.endswith("/logout")
        assert request.headers["Cookie"] == f"{COOKIE}=refresh-secret"
        return httpx.Response(204)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        store.login(client, "https://example.com/api/v1", "a@example.com", "password-secret")
        assert "password-secret" not in store.path.read_text()
        assert store.path.stat().st_mode & 0o777 == 0o600
        with pytest.raises(ConnectorError, match="already exists"):
            store.login(client, "https://example.com/api/v1", "a@example.com", "password-secret")
        store.logout(client)
        assert not store.path.exists()


def test_two_clients_rotate_once_and_reuse_fresh_session(store):
    store.write(Session("https://api.example.test/api/v1", "expired", "refresh-secret", 0))
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["Cookie"] == f"{COOKIE}=refresh-secret"
        return httpx.Response(
            200,
            json={"access_token": "new-access", "expires_in": 900},
            headers={"Set-Cookie": f"{COOKIE}=new-refresh; Secure; Path=/"},
        )

    def token(_):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            return SessionStore(store.path).authority(client).access_token

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(token, range(2))) == ["new-access", "new-access"]
    assert len(calls) == 1
    assert store.read().refresh_token == "new-refresh"


def test_revoked_refresh_fails_without_using_old_access(store):
    store.write(Session("https://api.example.test/api/v1", "expired", "refresh-secret", 0))
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(401, json={"detail": "invalid"})

    response = call(store, handler, "whoami")
    assert response.is_error
    assert len(seen) == 1
    assert seen[0].url.path.endswith("/auth/refresh")


def test_reject_shared_and_symlink_session_files(store, tmp_path):
    os.chmod(store.path, 0o644)
    with pytest.raises(ConnectorError, match="private"):
        store.read()
    os.chmod(store.path, 0o600)
    link = tmp_path / "link.json"
    link.symlink_to(store.path)
    with pytest.raises(ConnectorError, match="private"):
        SessionStore(link).read()


def test_password_change_required_is_not_stored(tmp_path):
    store = SessionStore(tmp_path / "session.json")
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "access_token": "restricted",
                        "expires_in": 300,
                        "must_change_password": True,
                    },
                )
            )
        ) as client,
        pytest.raises(ConnectorError, match="Change your password"),
    ):
        store.login(client, "https://example.com/api/v1", "a@example.com", "secret")
    assert not store.path.exists()


def test_failed_logout_retains_revocable_session(store):
    with (
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client,
        pytest.raises(ConnectorError, match="retained"),
    ):
        store.logout(client)
    assert store.path.exists()


@pytest.mark.parametrize("body", [[], {}, {"access_token": "secret", "expires_in": 0}])
def test_malformed_auth_response_is_safe_and_never_stored(tmp_path, body):
    store = SessionStore(tmp_path / "session.json")
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
        ) as client,
        pytest.raises(ConnectorError, match="Invalid authentication response"),
    ):
        store.login(client, "https://example.com/api/v1", "a@example.com", "secret")
    assert not store.path.exists()


def test_read_only_exposes_only_allowlisted_query_posts(store):
    async def run():
        with httpx.Client() as http:
            async with Client(create_server(ApiClient(store, http), read_only=True)) as client:
                names = {tool.name for tool in (await client.list_tools()).tools}
                assert {
                    "get_translation_suggestions",
                    "resolve_translation_suggestion",
                    "match_glossary_terms",
                } <= names
                assert (
                    not {
                        "save_new_entry",
                        "review_new_entry",
                        "save_glossary_term",
                        "delete_glossary_term",
                    }
                    & names
                )

    asyncio.run(run())
