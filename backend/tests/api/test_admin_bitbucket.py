"""Administrator-only Bitbucket client-credentials HTTP contracts."""

from __future__ import annotations

import asyncio
import base64
import os
from collections.abc import Generator, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.api.v1.routes.admin_bitbucket import get_bitbucket_oauth_service
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.services.bitbucket_oauth import (
    BitbucketOAuthService,
    OAuthConnectionUnavailable,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
SIGNING_SECRET = "0123456789abcdef" * 2
FERNET_KEY = base64.urlsafe_b64encode(b"2" * 32).decode()
BITBUCKET_PATH = "/api/v1/admin/bitbucket"
FIXED_NOW = datetime(2026, 8, 29, 15, 0, tzinfo=UTC)


@dataclass
class MutableClock:
    current: datetime = FIXED_NOW

    def __call__(self) -> datetime:
        return self.current


@dataclass
class FakeTokenExchange:
    """Exact-scope provider mock with no browser or revoke capability."""

    calls: list[dict[str, str]] = field(default_factory=list)
    error: Exception | None = None

    def exchange_client_credentials(
        self,
        *,
        client_id: str,
        client_secret: str,
    ) -> dict[str, object]:
        self.calls.append({"client_id": client_id, "client_secret": client_secret})
        if self.error is not None:
            raise self.error
        return {
            "access_token": "api-access-secret",  # pragma: allowlist secret
            "token_type": "bearer",
            "scope": "pullrequest:write repository repository:write pullrequest",
            "expires_in": 3600,
            "provider_body": "must-not-escape",
        }


@pytest.fixture(scope="module")
def bitbucket_api_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for the focused provider API."""
    database_name = f"verboflex_admin_bitbucket_{uuid4().hex}"
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
def clean_bitbucket_api_database(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    """Keep authority and singleton state independent across examples."""
    app.dependency_overrides.clear()
    app.openapi_schema = None
    with bitbucket_api_session_factory.begin() as session:
        session.execute(delete(AuthSession))
        session.execute(delete(User))
        connection = session.get(BitbucketConnection, 1)
        if connection is None:
            session.add(BitbucketConnection(id=1))
        else:
            connection.generation = 0
            connection.access_token_ciphertext = None
            connection.refresh_token_ciphertext = None
            connection.scope_profile = None
            connection.provider_expires_at = None
            connection.connected_at = None
            connection.revoked_at = None
    yield
    app.dependency_overrides.clear()
    app.openapi_schema = None


def oauth_settings() -> Settings:
    return Settings(
        jwt_secret_key=SecretStr(SIGNING_SECRET),
        bitbucket_oauth_client_id="verboflex-api-client",
        bitbucket_oauth_client_secret=SecretStr("backend-client-secret"),
        bitbucket_token_encryption_keyring=SecretStr(FERNET_KEY),
    )


def create_authority(
    factory: sessionmaker[Session],
    *,
    email: str,
    roles: Sequence[str],
) -> tuple[UUID, str]:
    """Persist one current principal and return its bearer authority."""
    user_id = uuid4()
    auth_session_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        durable_roles = list(session.execute(select(Role).where(Role.name.in_(roles))).scalars())
        session.add(
            User(
                id=user_id,
                email=email,
                display_name=email.split("@", 1)[0].title(),
                hashed_password=hash_password("principal password phrase!"),
                is_active=True,
                must_change_password=False,
                roles=durable_roles,
            )
        )
        session.add(
            AuthSession(
                id=auth_session_id,
                user_id=user_id,
                family_id=uuid4(),
                token_hash=uuid4().hex + uuid4().hex,
                expires_at=now + timedelta(days=7),
            )
        )
    token = issue_access_token(
        user_id=user_id,
        session_id=auth_session_id,
        token_version=0,
        purpose="access",
        settings=oauth_settings(),
        now=now,
    )
    return user_id, token


def configure_dependencies(
    factory: sessionmaker[Session],
    service: BitbucketOAuthService | None,
) -> None:
    """Wire principal, provider, and route sessions to controlled boundaries."""

    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = oauth_settings
    app.dependency_overrides[get_bitbucket_oauth_service] = lambda: service


async def bitbucket_request(
    method: str,
    *,
    path: str,
    access_token: str | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, headers=headers)


def connection_snapshot(factory: sessionmaker[Session]) -> tuple[object, ...]:
    with factory() as session:
        connection = session.get(BitbucketConnection, 1)
        assert connection is not None
        return (
            connection.generation,
            connection.access_token_ciphertext,
            connection.refresh_token_ciphertext,
            connection.scope_profile,
            connection.connected_at,
            connection.provider_expires_at,
            connection.revoked_at,
        )


def assert_bounded_status(response: httpx.Response, expected: str) -> dict[str, Any]:
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {
        "status",
        "scope_profile",
        "scope_label",
        "capability_profile",
        "connected_at",
        "expires_at",
        "revoked_at",
    }
    assert body["status"] == expected
    assert body["scope_profile"] == "repository_and_pull_request"
    assert body["scope_label"] == "Repository and pull-request access"
    profile = body["capability_profile"]
    assert set(profile) == {
        "source_read",
        "source_write",
        "pull_request",
        "evaluated_at",
    }
    expected_readiness = {
        "Connected": ("ready", "ready_for_later_phase", "ready_for_later_phase"),
        "Disconnected": ("disconnected", "disconnected", "disconnected"),
        "Reauthorization required": (
            "reauthorization_required",
            "reauthorization_required",
            "reauthorization_required",
        ),
        "Unavailable": ("unavailable", "unavailable", "unavailable"),
    }[expected]
    assert (
        profile["source_read"],
        profile["source_write"],
        profile["pull_request"],
    ) == expected_readiness
    if profile["evaluated_at"] is not None:
        evaluated_at = datetime.fromisoformat(profile["evaluated_at"].replace("Z", "+00:00"))
        assert evaluated_at.tzinfo is not None
    return body


def collect_mapping_keys(value: object) -> set[str]:
    """Collect nested response keys for recursive secret-surface assertions."""
    if isinstance(value, dict):
        return {
            *(str(key).casefold() for key in value),
            *(key for child in value.values() for key in collect_mapping_keys(child)),
        }
    if isinstance(value, list):
        return {key for child in value for key in collect_mapping_keys(child)}
    return set()


def test_admin_client_credentials_connect_reconnect_status_and_revoke(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> None:
    """Direct admin operations exchange only on the backend and return bounded status."""
    admin_id, admin_token = create_authority(
        bitbucket_api_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    exchange = FakeTokenExchange()
    service = BitbucketOAuthService(
        settings=oauth_settings(), token_exchange=exchange, clock=lambda: FIXED_NOW
    )
    configure_dependencies(bitbucket_api_session_factory, service)

    initial = asyncio.run(bitbucket_request("GET", path=BITBUCKET_PATH, access_token=admin_token))
    assert_bounded_status(initial, "Disconnected")

    connected = asyncio.run(
        bitbucket_request("POST", path=f"{BITBUCKET_PATH}/connect", access_token=admin_token)
    )
    connected_body = assert_bounded_status(connected, "Connected")
    assert connected_body["connected_at"] == FIXED_NOW.isoformat().replace("+00:00", "Z")
    assert connected_body["expires_at"] == (FIXED_NOW + timedelta(hours=1)).isoformat().replace(
        "+00:00", "Z"
    )
    assert exchange.calls == [
        {
            "client_id": "verboflex-api-client",
            "client_secret": "backend-client-secret",  # pragma: allowlist secret
        }
    ]
    first_snapshot = connection_snapshot(bitbucket_api_session_factory)
    assert first_snapshot[0] == 1
    assert first_snapshot[1] not in (None, "api-access-secret")
    assert first_snapshot[2] is None
    assert first_snapshot[3] == "pullrequest:write"

    reconnected = asyncio.run(
        bitbucket_request("POST", path=f"{BITBUCKET_PATH}/reconnect", access_token=admin_token)
    )
    assert_bounded_status(reconnected, "Connected")
    assert len(exchange.calls) == 2
    assert connection_snapshot(bitbucket_api_session_factory)[0] == 2

    revoked = asyncio.run(
        bitbucket_request("POST", path=f"{BITBUCKET_PATH}/revoke", access_token=admin_token)
    )
    revoked_body = assert_bounded_status(revoked, "Disconnected")
    assert revoked_body["revoked_at"] is not None
    assert connection_snapshot(bitbucket_api_session_factory)[0:4] == (
        3,
        None,
        None,
        "pullrequest:write",
    )
    assert admin_id


def test_client_credentials_status_uses_exact_expiry_boundary(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> None:
    """Public status changes to recovery state exactly at provider expiry."""
    _admin_id, admin_token = create_authority(
        bitbucket_api_session_factory,
        email="expiry-admin@example.com",
        roles=("admin",),
    )
    clock = MutableClock()
    service = BitbucketOAuthService(
        settings=oauth_settings(), token_exchange=FakeTokenExchange(), clock=clock
    )
    configure_dependencies(bitbucket_api_session_factory, service)
    asyncio.run(
        bitbucket_request("POST", path=f"{BITBUCKET_PATH}/connect", access_token=admin_token)
    )

    clock.current += timedelta(seconds=3599)
    before = asyncio.run(bitbucket_request("GET", path=BITBUCKET_PATH, access_token=admin_token))
    assert_bounded_status(before, "Connected")
    clock.current += timedelta(seconds=1)
    expired = asyncio.run(bitbucket_request("GET", path=BITBUCKET_PATH, access_token=admin_token))
    assert_bounded_status(expired, "Reauthorization required")


def test_legacy_authority_projects_reauthorization_required_capability(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> None:
    """Expose only closed recovery readiness for a superseded read-only grant."""
    _admin_id, admin_token = create_authority(
        bitbucket_api_session_factory,
        email="legacy-capability-admin@example.com",
        roles=("admin",),
    )
    service = BitbucketOAuthService(
        settings=oauth_settings(),
        token_exchange=FakeTokenExchange(),
        clock=lambda: FIXED_NOW,
    )
    configure_dependencies(bitbucket_api_session_factory, service)
    connected = asyncio.run(
        bitbucket_request("POST", path=f"{BITBUCKET_PATH}/connect", access_token=admin_token)
    )
    assert_bounded_status(connected, "Connected")
    with bitbucket_api_session_factory.begin() as session:
        connection = session.get_one(BitbucketConnection, 1)
        connection.scope_profile = "repository"

    legacy = asyncio.run(bitbucket_request("GET", path=BITBUCKET_PATH, access_token=admin_token))
    assert_bounded_status(legacy, "Reauthorization required")


def test_capability_projection_is_recursive_forbidden_field_free(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> None:
    """Keep provider authority, credentials, identity, and mutations out of status."""
    _admin_id, admin_token = create_authority(
        bitbucket_api_session_factory,
        email="closed-capability-admin@example.com",
        roles=("admin",),
    )
    configure_dependencies(bitbucket_api_session_factory, None)

    unavailable = asyncio.run(
        bitbucket_request("GET", path=BITBUCKET_PATH, access_token=admin_token)
    )
    body = assert_bounded_status(unavailable, "Unavailable")
    forbidden = {
        "access_token",
        "authorization",
        "branch",
        "ciphertext",
        "client_id",
        "client_secret",
        "commit",
        "effective_scope",
        "generation",
        "provider_body",
        "raw_scope",
        "refresh_token",
        "scope",
        "source_generation",
        "workspace",
    }
    assert collect_mapping_keys(body).isdisjoint(forbidden)


def test_connect_reconnect_status_require_current_admin_without_mutation(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> None:
    """Deny anonymous and viewer callers before provider or singleton mutation."""
    _admin_id, admin_token = create_authority(
        bitbucket_api_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    _viewer_id, viewer_token = create_authority(
        bitbucket_api_session_factory,
        email="viewer@example.com",
        roles=("viewer",),
    )
    exchange = FakeTokenExchange()
    service = BitbucketOAuthService(settings=oauth_settings(), token_exchange=exchange)
    configure_dependencies(bitbucket_api_session_factory, service)
    before = connection_snapshot(bitbucket_api_session_factory)

    protected = (
        ("GET", BITBUCKET_PATH),
        ("POST", f"{BITBUCKET_PATH}/connect"),
        ("POST", f"{BITBUCKET_PATH}/reconnect"),
        ("POST", f"{BITBUCKET_PATH}/revoke"),
    )
    for method, path in protected:
        anonymous = asyncio.run(bitbucket_request(method, path=path))
        viewer = asyncio.run(bitbucket_request(method, path=path, access_token=viewer_token))
        assert anonymous.status_code == 401
        assert viewer.status_code == 403

    assert connection_snapshot(bitbucket_api_session_factory) == before
    assert exchange.calls == []
    assert (
        asyncio.run(
            bitbucket_request("GET", path=BITBUCKET_PATH, access_token=admin_token)
        ).status_code
        == 200
    )


def test_client_credentials_capability_contract_has_no_forbidden_provider_fields() -> None:
    """OpenAPI exposes the four bounded administrator operations only."""
    schema = app.openapi()
    provider_paths = {path for path in schema["paths"] if path.startswith(BITBUCKET_PATH)}
    assert provider_paths == {
        BITBUCKET_PATH,
        f"{BITBUCKET_PATH}/connect",
        f"{BITBUCKET_PATH}/reconnect",
        f"{BITBUCKET_PATH}/revoke",
    }
    assert (
        schema["paths"][f"{BITBUCKET_PATH}/connect"]["post"]["operationId"]
        == "connect_admin_bitbucket_oauth"
    )
    assert (
        schema["paths"][f"{BITBUCKET_PATH}/reconnect"]["post"]["operationId"]
        == "reconnect_admin_bitbucket_oauth"
    )
    properties = schema["components"]["schemas"]["AdminBitbucketStatusResponse"]["properties"]
    assert set(properties) == {
        "status",
        "scope_profile",
        "scope_label",
        "capability_profile",
        "connected_at",
        "expires_at",
        "revoked_at",
    }
    capability_schema = schema["components"]["schemas"]["AdminBitbucketCapabilityProfile"]
    assert capability_schema["additionalProperties"] is False
    assert set(capability_schema["properties"]) == {
        "source_read",
        "source_write",
        "pull_request",
        "evaluated_at",
    }
    provider_contract = {
        "paths": {path: schema["paths"][path] for path in provider_paths},
        "status_schema": schema["components"]["schemas"]["AdminBitbucketStatusResponse"],
        "error_schema": schema["components"]["schemas"]["AdminBitbucketErrorResponse"],
    }
    serialized = str(provider_contract).casefold()
    for forbidden in (
        "authorization_url",
        "callback",
        "workspace",
        "access_token",
        "refresh_token",
        "client_secret",
        "source_generation",
        "raw_scope",
        "effective_scope",
        "provider_body",
    ):
        assert forbidden not in serialized


def test_client_credentials_connect_failure_is_bounded(
    bitbucket_api_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider diagnostics never escape direct connection failures."""
    _admin_id, admin_token = create_authority(
        bitbucket_api_session_factory,
        email="failure-admin@example.com",
        roles=("admin",),
    )
    exchange = FakeTokenExchange(error=RuntimeError("provider-body-must-not-escape"))
    service = BitbucketOAuthService(settings=oauth_settings(), token_exchange=exchange)
    configure_dependencies(bitbucket_api_session_factory, service)

    failed = asyncio.run(
        bitbucket_request("POST", path=f"{BITBUCKET_PATH}/connect", access_token=admin_token)
    )
    assert failed.status_code == 503
    assert failed.json() == {"detail": "Bitbucket connection unavailable"}
    assert failed.headers["cache-control"] == "no-store"
    assert "provider-body" not in failed.text

    configure_dependencies(bitbucket_api_session_factory, None)
    unavailable = asyncio.run(
        bitbucket_request(
            "POST",
            path=f"{BITBUCKET_PATH}/connect",
            access_token=admin_token,
        )
    )
    assert unavailable.status_code == 503
    assert unavailable.json() == {"detail": "Bitbucket connection unavailable"}
    assert unavailable.headers["cache-control"] == "no-store"

    configure_dependencies(bitbucket_api_session_factory, service)

    def fail_revoke(_session: Session, *, actor_id: UUID) -> None:
        assert actor_id == _admin_id
        raise OAuthConnectionUnavailable("provider detail must remain bounded")

    monkeypatch.setattr(service, "revoke_current", fail_revoke)
    revoke_failure = asyncio.run(
        bitbucket_request(
            "POST",
            path=f"{BITBUCKET_PATH}/revoke",
            access_token=admin_token,
        )
    )
    assert revoke_failure.status_code == 503
    assert revoke_failure.json() == {"detail": "Bitbucket connection unavailable"}
    assert "provider detail" not in revoke_failure.text


def test_local_revoke_remains_available_without_provider_configuration(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> None:
    """An admin can clear local authority even when provider settings are unavailable."""
    _admin_id, admin_token = create_authority(
        bitbucket_api_session_factory,
        email="revoke-without-settings-admin@example.com",
        roles=("admin",),
    )
    service = BitbucketOAuthService(
        settings=oauth_settings(),
        token_exchange=FakeTokenExchange(),
        clock=lambda: FIXED_NOW,
    )
    configure_dependencies(bitbucket_api_session_factory, service)
    connected = asyncio.run(
        bitbucket_request(
            "POST",
            path=f"{BITBUCKET_PATH}/connect",
            access_token=admin_token,
        )
    )
    assert_bounded_status(connected, "Connected")
    before = connection_snapshot(bitbucket_api_session_factory)
    assert before[0] == 1
    assert before[1] is not None

    configure_dependencies(bitbucket_api_session_factory, None)
    revoked = asyncio.run(
        bitbucket_request(
            "POST",
            path=f"{BITBUCKET_PATH}/revoke",
            access_token=admin_token,
        )
    )

    revoked_body = assert_bounded_status(revoked, "Disconnected")
    assert revoked_body["revoked_at"] is not None
    after = connection_snapshot(bitbucket_api_session_factory)
    assert after[0] == 2
    assert after[1:3] == (None, None)
    assert after[5] is None
    assert after[6] is not None
