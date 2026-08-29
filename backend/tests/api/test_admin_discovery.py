"""Administrator branch-discovery API contracts."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.integrations.bitbucket.client import (
    BitbucketBranch,
    BitbucketProviderReadError,
    BitbucketSourceEntry,
    BitbucketSourcePage,
)
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.repository import Repository
from verboflex.models.role import Role
from verboflex.models.user import User

SIGNING_SECRET = "0123456789abcdef" * 2
DISCOVERY_PATH = "/api/v1/admin/repositories"
BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)


@pytest.fixture(scope="module")
def discovery_session_factory() -> Generator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for branch discovery."""
    database_name = f"verboflex_admin_discovery_{uuid4().hex}"
    with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
        admin_connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )
    database_url = ADMIN_DATABASE_URL.rsplit("/", 1)[0] + f"/{database_name}"
    sqlalchemy_url = database_url.replace("postgresql://", "postgresql+psycopg://")
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlalchemy_url)
    engine = create_engine(sqlalchemy_url)
    command.upgrade(config, "head")
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    try:
        yield factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


@pytest.fixture(autouse=True)
def clean_discovery_database(
    discovery_session_factory: sessionmaker[Session],
) -> Generator[None]:
    app.dependency_overrides.clear()
    with discovery_session_factory.begin() as session:
        session.execute(delete(AuthSession))
        session.execute(delete(User))
        session.execute(delete(Repository))
    yield
    app.dependency_overrides.clear()


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(SIGNING_SECRET))


def _configure(factory: sessionmaker[Session], adapter: object) -> None:
    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = _settings
    try:
        from verboflex.api.v1.routes.admin_discovery import get_bitbucket_discovery_adapter
    except ModuleNotFoundError:
        return
    app.dependency_overrides[get_bitbucket_discovery_adapter] = lambda: adapter


def _authority(factory: sessionmaker[Session], *, role: str, email: str) -> str:
    user_id = uuid4()
    auth_session_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        durable_role = session.scalar(select(Role).where(Role.name == role))
        assert durable_role is not None
        session.add(
            User(
                id=user_id,
                email=email,
                display_name=email,
                hashed_password=hash_password("principal password phrase!"),
                is_active=True,
                must_change_password=False,
                roles=[durable_role],
            )
        )
        session.add(
            AuthSession(
                id=auth_session_id,
                user_id=user_id,
                family_id=uuid4(),
                token_hash=uuid4().hex + uuid4().hex,
                expires_at=now + timedelta(days=1),
            )
        )
    return issue_access_token(
        user_id=user_id,
        session_id=auth_session_id,
        token_version=0,
        purpose="access",
        settings=_settings(),
        now=now,
    )


def _repository(factory: sessionmaker[Session]) -> UUID:
    repository_id = uuid4()
    with factory.begin() as session:
        session.add(
            Repository(
                id=repository_id,
                workspace="acme",
                repository_slug="mobile",
                descriptive_name="Mobile",
                descriptive_name_key="mobile",
            )
        )
    return repository_id


async def _request(
    path: str,
    *,
    token: str | None,
    params: Mapping[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    headers = {"Authorization": f"Bearer {token}"} if token is not None else None
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers, params=params)


@dataclass
class FakeDiscoveryAdapter:
    branches: tuple[FakeBranch, ...]
    failure_kind: str | None = None
    calls: list[tuple[str, str]] = field(default_factory=list)
    resolve_calls: list[tuple[str, str, str]] = field(default_factory=list)
    source_bodies: dict[str, bytes] = field(default_factory=dict)
    source_calls: list[str] = field(default_factory=list)

    async def list_repository_branches(
        self,
        _session: Session,
        *,
        workspace: str,
        repository_slug: str,
    ) -> tuple[BitbucketBranch, ...]:
        self.calls.append((workspace, repository_slug))
        if self.failure_kind is not None:
            from verboflex.integrations.bitbucket.client import BitbucketProviderReadError

            raise BitbucketProviderReadError(kind=self.failure_kind)
        return self.branches

    async def resolve_repository_branch(
        self,
        _session: Session,
        *,
        workspace: str,
        repository_slug: str,
        branch: str,
    ) -> BitbucketBranch:
        self.resolve_calls.append((workspace, repository_slug, branch))
        self.source_calls.append(f"resolve:{workspace}/{repository_slug}:{branch}")
        if self.failure_kind is not None:
            raise BitbucketProviderReadError(kind=self.failure_kind)
        return BitbucketBranch(name=branch, commit_hash="a" * 40)

    async def list_repository_source_page(
        self,
        _session: Session,
        *,
        directory_path: str | None,
        **_kwargs: object,
    ) -> BitbucketSourcePage:
        self.source_calls.append(f"tree:{directory_path or '/'}")
        return BitbucketSourcePage(
            entries=tuple(
                BitbucketSourceEntry(path=path, kind="file", size=len(body))
                for path, body in self.source_bodies.items()
            ),
            next_url=None,
        )

    async def read_repository_source_file(
        self,
        _session: Session,
        *,
        path: str,
        **_kwargs: object,
    ) -> bytes:
        self.source_calls.append(f"raw:{path}")
        return self.source_bodies[path]


@dataclass(frozen=True)
class FakeBranch:
    name: str
    commit_hash: str


@pytest.mark.parametrize(
    "branch_name",
    [
        "feature/foo",
        "percent%branch",
        "unicodé/分支",
        "space branch",
        "what?branch",
        "hash#branch",
        "reserved:[]@!$&'()*+,;=",
    ],
)
def test_exact_branch_query_round_trips_opaque_names_without_list_scans(
    discovery_session_factory: sessionmaker[Session],
    branch_name: str,
) -> None:
    """Configured branch lookup uses one exact safe-adapter detail request."""
    branches = tuple(
        FakeBranch(name=f"listed-{index:03d}", commit_hash=f"{index:040x}") for index in range(100)
    ) + (FakeBranch(name=branch_name, commit_hash="f" * 40),)
    adapter = FakeDiscoveryAdapter(branches=branches)
    _configure(discovery_session_factory, adapter)
    token = _authority(
        discovery_session_factory,
        role="admin",
        email=f"exact-{uuid4()}@example.com",
    )
    repository_id = _repository(discovery_session_factory)
    path = f"{DISCOVERY_PATH}/{repository_id}/branch"

    response = asyncio.run(
        _request(
            path,
            token=token,
            params={"branch_name": branch_name},
        )
    )

    assert response.status_code == 200
    assert response.json() == {"name": branch_name, "commit_hash": "a" * 40}
    assert set(response.json()) == {"name", "commit_hash"}
    assert adapter.resolve_calls == [("acme", "mobile", branch_name)]
    assert adapter.calls == []


@pytest.mark.parametrize(
    ("failure_kind", "status_code"),
    [
        ("not_found", 404),
        ("reauthorization_required", 409),
        ("invalid_source", 422),
        ("limit_exceeded", 422),
    ],
)
def test_exact_branch_query_is_required_owned_and_bounded(
    discovery_session_factory: sessionmaker[Session],
    failure_kind: str,
    status_code: int,
) -> None:
    """Missing repositories and safe-adapter failures retain the closed contract."""
    adapter = FakeDiscoveryAdapter(branches=(), failure_kind=failure_kind)
    _configure(discovery_session_factory, adapter)
    token = _authority(
        discovery_session_factory,
        role="admin",
        email=f"exact-failure-{failure_kind}@example.com",
    )
    repository_id = _repository(discovery_session_factory)
    path = f"{DISCOVERY_PATH}/{repository_id}/branch"

    failure = asyncio.run(_request(path, token=token, params={"branch_name": "configured/exact"}))
    assert failure.status_code == status_code
    assert failure.json() == {
        "detail": "Bitbucket discovery unavailable",
        "state": failure_kind,
    }
    assert adapter.resolve_calls == [("acme", "mobile", "configured/exact")]
    assert adapter.calls == []

    missing_repository = asyncio.run(
        _request(
            f"{DISCOVERY_PATH}/{uuid4()}/branch",
            token=token,
            params={"branch_name": "configured/exact"},
        )
    )
    assert missing_repository.status_code == 404
    assert missing_repository.json() == {"detail": "Repository unavailable"}
    assert len(adapter.resolve_calls) == 1

    calls_before_invalid = len(adapter.resolve_calls)
    assert asyncio.run(_request(path, token=token)).status_code == 422
    assert asyncio.run(_request(path, token=token, params={"branch_name": ""})).status_code == 422
    assert (
        asyncio.run(_request(path, token=token, params={"branch_name": "x" * 256})).status_code
        == 422
    )
    assert len(adapter.resolve_calls) == calls_before_invalid


def test_discovery_openapi_keeps_exact_branch_and_cursor_contracts_closed() -> None:
    """Exact lookup is required while collection continuations stay application-owned."""
    openapi = app.openapi()
    exact_operation = openapi["paths"]["/api/v1/admin/repositories/{repository_id}/branch"]["get"]
    branch_parameter = next(
        parameter
        for parameter in exact_operation["parameters"]
        if parameter["name"] == "branch_name"
    )
    assert branch_parameter["in"] == "query"
    assert branch_parameter["required"] is True
    assert branch_parameter["schema"]["minLength"] == 1
    assert branch_parameter["schema"]["maxLength"] == 255
    assert exact_operation["operationId"] == "get_admin_repository_branch"

    branch_list_schema = openapi["components"]["schemas"]["AdminBranchListResponse"]
    assert set(branch_list_schema["properties"]) == {"items", "next_cursor"}
    assert branch_list_schema["required"] == ["items", "next_cursor"]
    assert "provider" not in str(branch_list_schema).casefold()
    assert "url" not in str(branch_list_schema).casefold()


def test_admin_branch_collection_is_exact_bounded_and_application_opaque(
    discovery_session_factory: sessionmaker[Session],
) -> None:
    """Default/max pages slice provider order and malformed inputs never call Bitbucket."""
    branches = tuple(
        FakeBranch(name=f"Branch-{index:03d}", commit_hash=f"{index:040x}") for index in range(120)
    )
    adapter = FakeDiscoveryAdapter(branches=branches)
    _configure(discovery_session_factory, adapter)
    token = _authority(discovery_session_factory, role="admin", email="admin@example.com")
    repository_id = _repository(discovery_session_factory)
    path = f"{DISCOVERY_PATH}/{repository_id}/branches"

    first = asyncio.run(_request(path, token=token))
    assert first.status_code == 200
    assert [item["name"] for item in first.json()["items"]] == [
        branch.name for branch in branches[:50]
    ]
    cursor = first.json()["next_cursor"]
    assert isinstance(cursor, str)
    assert "bitbucket" not in cursor.lower()
    assert "http" not in cursor.lower()

    second = asyncio.run(_request(f"{path}?limit=100&cursor={cursor}", token=token))
    assert second.status_code == 200
    assert [item["name"] for item in second.json()["items"]] == [
        branch.name for branch in branches[50:]
    ]
    assert second.json()["next_cursor"] is None

    calls_before_invalid = len(adapter.calls)
    invalid_cursor = asyncio.run(_request(f"{path}?cursor=not-a-cursor", token=token))
    oversized_page = asyncio.run(_request(f"{path}?limit=101", token=token))
    assert invalid_cursor.status_code == 422
    assert oversized_page.status_code == 422
    assert len(adapter.calls) == calls_before_invalid


def test_denied_or_unregistered_discovery_never_calls_provider(
    discovery_session_factory: sessionmaker[Session],
) -> None:
    adapter = FakeDiscoveryAdapter(branches=())
    _configure(discovery_session_factory, adapter)
    viewer = _authority(discovery_session_factory, role="viewer", email="viewer@example.com")
    missing_path = f"{DISCOVERY_PATH}/{uuid4()}/branches"

    anonymous = asyncio.run(_request(missing_path, token=None))
    forbidden = asyncio.run(_request(missing_path, token=viewer))
    assert anonymous.status_code == 401
    assert forbidden.status_code == 403
    assert adapter.calls == []

    admin = _authority(discovery_session_factory, role="admin", email="admin@example.com")
    missing = asyncio.run(_request(missing_path, token=admin))
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Repository unavailable"}
    assert adapter.calls == []


@pytest.mark.parametrize(
    ("kind", "status_code", "state"),
    [
        ("disconnected", 409, "disconnected"),
        ("reauthorization_required", 409, "reauthorization_required"),
        ("permission_denied", 403, "permission_denied"),
        ("not_found", 404, "not_found"),
        ("unavailable", 503, "unavailable"),
        ("timeout", 504, "timeout"),
    ],
)
def test_provider_failures_are_typed_bounded_states(
    discovery_session_factory: sessionmaker[Session],
    kind: str,
    status_code: int,
    state: str,
) -> None:
    adapter = FakeDiscoveryAdapter(branches=(), failure_kind=kind)
    _configure(discovery_session_factory, adapter)
    token = _authority(discovery_session_factory, role="admin", email=f"{kind}@example.com")
    repository_id = _repository(discovery_session_factory)

    response = asyncio.run(_request(f"{DISCOVERY_PATH}/{repository_id}/branches", token=token))
    assert response.status_code == status_code
    assert response.json() == {
        "detail": "Bitbucket discovery unavailable",
        "state": state,
    }
    assert adapter.calls == [("acme", "mobile")]


def test_admin_source_discovery_returns_metadata_only_and_maps_closed_failures(
    discovery_session_factory: sessionmaker[Session],
) -> None:
    adapter = FakeDiscoveryAdapter(
        branches=(),
        source_bodies={"locales/en.json": b'{"hello":"Hello"}\n'},
    )
    _configure(discovery_session_factory, adapter)
    token = _authority(discovery_session_factory, role="admin", email="source@example.com")
    repository_id = _repository(discovery_session_factory)
    path = f"{DISCOVERY_PATH}/{repository_id}/sources?branch=Main"

    success = asyncio.run(_request(path, token=token))
    assert success.status_code == 200
    assert success.json() == {
        "commit_hash": "a" * 40,
        "files": [{"path": "locales/en.json", "size": 18}],
        "total_bytes": 18,
    }
    assert "Hello" not in success.text
    assert adapter.source_calls == [
        "resolve:acme/mobile:Main",
        "tree:/",
        "raw:locales/en.json",
    ]

    adapter.failure_kind = "invalid_source"
    failure = asyncio.run(_request(path, token=token))
    assert failure.status_code == 422
    assert failure.json() == {
        "detail": "Bitbucket discovery unavailable",
        "state": "invalid_source",
    }


def test_admin_source_discovery_handles_missing_adapter_and_repository_without_provider_calls(
    discovery_session_factory: sessionmaker[Session],
) -> None:
    token = _authority(discovery_session_factory, role="admin", email="missing@example.com")
    repository_id = _repository(discovery_session_factory)
    _configure(discovery_session_factory, None)
    unavailable = asyncio.run(
        _request(f"{DISCOVERY_PATH}/{repository_id}/sources?branch=main", token=token)
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["state"] == "unavailable"

    adapter = FakeDiscoveryAdapter(branches=())
    _configure(discovery_session_factory, adapter)
    missing = asyncio.run(_request(f"{DISCOVERY_PATH}/{uuid4()}/sources?branch=main", token=token))
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Repository unavailable"}
    assert adapter.source_calls == []
