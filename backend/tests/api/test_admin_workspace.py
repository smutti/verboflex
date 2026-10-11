"""Workspace settings and adapter-to-API picker contracts on isolated Postgres."""

import asyncio
from urllib.parse import urlencode
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from tests.api.test_admin_repositories import (  # noqa: F401
    clean_repository_api_database,
    configure_dependencies,
    create_authority,
    repository_api_session_factory,
    repository_request,
)
from tests.integration.test_bitbucket_http_adapter import FakeCredentialLeaseAuthority
from verboflex.api.v1.routes.admin_discovery import (
    get_bitbucket_discovery_adapter,
    get_repository_discovery_adapter,
)
from verboflex.auth.rate_limits import BoundedLocalRateLimiter, get_local_rate_limiter
from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.integrations.github.client import GitHubHttpAdapter
from verboflex.integrations.readers import RepositoryReadAdapters
from verboflex.main import app
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.repository import Repository

BASE = "/api/v1/admin/bitbucket"


@pytest.fixture
def context(repository_api_session_factory):  # noqa: F811
    factory = repository_api_session_factory
    configure_dependencies(factory)
    token = create_authority(factory, email=f"admin-{uuid4()}@example.com", roles=["admin"])
    with factory.begin() as session:
        session.execute(select(BitbucketConnection))
        connection = session.get(BitbucketConnection, 1)
        if connection:
            connection.workspace = None
            connection.generation = 7
        else:
            session.add(BitbucketConnection(id=1, generation=7))
    requests = []

    def provider(request):
        requests.append(request)
        workspace = request.url.path.split("/")[3]
        if request.url.path.endswith("/missing"):
            return httpx.Response(404, text="secret provider body")
        if request.url.params.get("q") == 'name ~ "ratelimit" OR slug ~ "ratelimit"':
            return httpx.Response(429, text="secret provider body")
        item = {"slug": "mobile", "name": "Mobile", "workspace": {"slug": workspace}}
        if request.url.path.endswith("/mobile"):
            return httpx.Response(200, headers={"x-oauth-scopes": "pullrequest:write"}, json=item)
        if request.url.params.get("q") == 'name ~ "empty" OR slug ~ "empty"':
            return httpx.Response(
                200, headers={"x-oauth-scopes": "pullrequest:write"}, json={"values": []}
            )
        page = {"values": [item]}
        if "page" not in request.url.params:
            page["next"] = str(request.url.copy_set_param("page", "opaque-page-2"))
        return httpx.Response(200, headers={"x-oauth-scopes": "pullrequest:write"}, json=page)

    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=FakeCredentialLeaseAuthority(),
        transport=httpx.MockTransport(provider),
    )
    app.dependency_overrides[get_bitbucket_discovery_adapter] = lambda: adapter
    limiter = BoundedLocalRateLimiter()
    app.dependency_overrides[get_local_rate_limiter] = lambda: limiter
    yield factory, token, requests
    asyncio.run(adapter.aclose())


def call(context, method, suffix, body=None, token_override="default"):
    token = context[1] if token_override == "default" else token_override
    return asyncio.run(
        repository_request(method, access_token=token, path=BASE + suffix, json_body=body)
    )


def test_workspace_is_admin_only_normalized_and_preserves_connection(context):
    assert call(context, "GET", "/workspace", token_override=None).status_code == 401
    reader = create_authority(context[0], email="reader@example.com", roles=["translator"])
    for method, path, body in [
        ("GET", "/workspace", None),
        ("PUT", "/workspace", {"workspace": "acme"}),
        ("GET", "/repositories", None),
        ("PUT", "/repositories/mobile", {"workspace": "acme"}),
    ]:
        assert call(context, method, path, body, token_override=reader).status_code == 403
    assert call(context, "GET", "/workspace").json() == {"workspace": None}
    assert call(context, "PUT", "/workspace", {"workspace": " AcMe "}).json() == {
        "workspace": "acme"
    }
    assert call(context, "GET", "/workspace").json() == {"workspace": "acme"}
    with context[0]() as session:
        assert session.get(BitbucketConnection, 1).generation == 7
    assert context[2] == []


def test_concurrent_first_workspace_selection_has_one_audit_event(context):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy import delete, event

    from verboflex.models.audit import AuditEntry
    from verboflex.services.workspace_repositories import set_workspace

    factory = context[0]
    actor_id = uuid4()
    with factory.begin() as session:
        session.execute(delete(BitbucketConnection))
    barrier = Barrier(2)

    def before_insert(_connection, _cursor, statement, *_args):
        if statement.startswith("INSERT INTO bitbucket_connections "):
            barrier.wait(timeout=10)

    def choose():
        with factory() as session:
            return set_workspace(session, "acme", actor_id=actor_id)

    engine = factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", before_insert)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(choose), pool.submit(choose)
            assert first.result(timeout=15) == second.result(timeout=15) == "acme"
    finally:
        event.remove(engine, "before_cursor_execute", before_insert)
    with factory() as session:
        events = list(session.scalars(select(AuditEntry).where(AuditEntry.actor_id == actor_id)))
        assert [entry.action for entry in events] == ["workspace.updated"]


@pytest.mark.parametrize(
    "workspace", ["", "https://bitbucket.org/acme", "../other", "a/b", "a" * 101]
)
def test_workspace_rejects_non_identifiers(context, workspace):
    assert call(context, "PUT", "/workspace", {"workspace": workspace}).status_code == 422
    assert context[2] == []


def test_search_and_signed_pagination_are_bound_to_workspace_query_and_caller(context):
    assert call(context, "GET", "/repositories").status_code == 409
    call(context, "PUT", "/workspace", {"workspace": "acme"})
    query = 'mobile " OR name ~ "other'
    first = call(context, "GET", "/repositories?" + urlencode({"q": query, "limit": 20}))
    assert first.status_code == 200, first.text
    assert first.json()["items"] == [
        {"workspace": "acme", "repository_slug": "mobile", "name": "Mobile"}
    ]
    cursor = first.json()["next_cursor"]
    assert "https://" not in cursor
    assert len(context[2]) == 1
    assert context[2][0].url.path == "/2.0/repositories/acme"
    assert '\\"' in context[2][0].url.params["q"]
    second = call(
        context, "GET", "/repositories?" + urlencode({"q": query, "limit": 20, "cursor": cursor})
    )
    assert second.status_code == 200 and second.json()["next_cursor"] is None
    assert len(context[2]) == 2
    for changes in ({"q": "changed"}, {"limit": 10}, {"cursor": cursor[:-1] + "!"}):
        params = {"q": query, "limit": 20, "cursor": cursor, **changes}
        assert call(context, "GET", "/repositories?" + urlencode(params)).status_code == 422
    other_admin = create_authority(context[0], email="other@example.com", roles=["admin"])
    assert (
        call(
            context,
            "GET",
            "/repositories?" + urlencode({"q": query, "cursor": cursor}),
            token_override=other_admin,
        ).status_code
        == 422
    )
    call(context, "PUT", "/workspace", {"workspace": "other"})
    assert (
        call(
            context, "GET", "/repositories?" + urlencode({"q": query, "cursor": cursor})
        ).status_code
        == 422
    )
    assert len(context[2]) == 2


def test_selection_is_idempotent_reuses_registry_and_rejects_workspace_change(context):
    call(context, "PUT", "/workspace", {"workspace": "acme"})
    responses = [
        call(context, "PUT", "/repositories/mobile", {"workspace": "acme"}) for _ in range(2)
    ]
    assert all(result.status_code == 200 for result in responses), [r.text for r in responses]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    with context[0]() as session:
        assert len(list(session.scalars(select(Repository)))) == 1
    assert call(context, "PUT", "/repositories/mobile", {"workspace": "other"}).status_code == 409
    missing = call(context, "PUT", "/repositories/missing", {"workspace": "acme"})
    assert missing.status_code == 404 and "secret" not in missing.text
    assert len(context[2]) == 3


def test_empty_provider_rate_limit_and_invalid_query_are_bounded(context):
    call(context, "PUT", "/workspace", {"workspace": "acme"})
    assert call(context, "GET", "/repositories?q=empty").json()["items"] == []
    response = call(context, "GET", "/repositories?q=ratelimit")
    assert response.status_code == 429 and "secret" not in response.text
    assert call(context, "GET", "/repositories?limit=51").status_code == 422
    assert call(context, "GET", "/repositories?q=%00").status_code == 422
    assert len(context[2]) == 2


def test_workspace_rate_limit_prevents_extra_provider_requests(context):
    call(context, "PUT", "/workspace", {"workspace": "acme"})
    for _ in range(59):
        assert call(context, "GET", "/repositories?q=empty").status_code == 200
    limited = call(context, "GET", "/repositories?q=empty")
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
    assert limited.headers["X-RateLimit-Remaining"] == "0"
    assert len(context[2]) == 59


def test_workspace_picker_accepts_the_production_provider_pool(context):
    adapter = app.dependency_overrides[get_bitbucket_discovery_adapter]()
    github = GitHubHttpAdapter()
    app.dependency_overrides[get_repository_discovery_adapter] = lambda: RepositoryReadAdapters(
        adapter, github
    )
    try:
        assert call(context, "PUT", "/workspace", {"workspace": "sample"}).status_code == 200
        assert call(context, "GET", "/repositories").status_code == 200
        assert call(
            context, "PUT", "/repositories/mobile", {"workspace": "sample"}
        ).status_code in (200, 201)
    finally:
        asyncio.run(github.aclose())
