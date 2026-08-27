"""Administrator-only Bitbucket OAuth lifecycle HTTP contracts."""

from __future__ import annotations

import asyncio
import base64
import os
from collections.abc import Generator, Iterator, Sequence
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.message import Message
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import OpenerDirector, Request
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from fastapi import HTTPException
from psycopg import connect, sql
from pydantic import AnyHttpUrl, SecretStr
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.api.v1.routes.admin_bitbucket import (
    _session_id,
    get_bitbucket_oauth_service,
)
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.auth.principal import Principal
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.schemas.users import RoleName
from verboflex.services.bitbucket_oauth import (
    MAX_TOKEN_RESPONSE_BYTES,
    TOKEN_EXCHANGE_TIMEOUT_SECONDS,
    BitbucketOAuthService,
    BitbucketOAuthTokenExchange,
    OAuthCallbackRejected,
    OAuthConnectionUnavailable,
    _RejectRedirects,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
SIGNING_SECRET = "0123456789abcdef" * 2
FERNET_KEY = base64.urlsafe_b64encode(b"2" * 32).decode()
CALLBACK_URI = "https://api.verboflex.example/api/v1/admin/bitbucket/oauth/callback"
BITBUCKET_PATH = "/api/v1/admin/bitbucket"


@dataclass
class FakeRedis:
    """Atomic digest-only OAuth-state seam."""

    values: dict[str, str] = field(default_factory=dict)

    def set(self, name: str, value: str, *, ex: int, nx: bool) -> bool:
        if ex != 600 or not nx or name in self.values:
            return False
        self.values[name] = value
        return True

    def getdel(self, name: str) -> str | None:
        return self.values.pop(name, None)


@dataclass
class FakeTokenExchange:
    """Exact-scope provider mock with no revoke capability."""

    calls: list[dict[str, str]] = field(default_factory=list)
    error: Exception | None = None

    def exchange_authorization_code(
        self,
        *,
        code: str,
        callback_uri: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "code": code,
                "callback_uri": callback_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            }
        )
        if self.error is not None:
            raise self.error
        return {
            "access_token": "api-access-secret",  # pragma: allowlist secret
            "refresh_token": "api-refresh-secret",  # pragma: allowlist secret
            "scope": "repository",
            "expires_in": 3600,
            "provider_body": "must-not-escape",
        }

    def refresh_tokens(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, object]:
        if self.error is not None:
            raise self.error
        return {
            "access_token": "rotated-api-access-secret",  # pragma: allowlist secret
            "refresh_token": "rotated-api-refresh-secret",  # pragma: allowlist secret
            "scope": "repository",
            "expires_in": 3600,
        }


@dataclass
class FakeHTTPResponse:
    payload: bytes
    read_limits: list[int] = field(default_factory=list)

    def __enter__(self) -> FakeHTTPResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        self.read_limits.append(limit)
        return self.payload


@dataclass
class FakeOpener:
    response: FakeHTTPResponse | None = None
    error: Exception | None = None
    calls: list[tuple[Request, int]] = field(default_factory=list)

    def open(self, request: Request, *, timeout: int) -> FakeHTTPResponse:
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


@dataclass
class FakeStatusSession:
    """Expose one structurally corrupt row without bypassing the database constraint."""

    connection: BitbucketConnection

    def begin(self) -> nullcontext[None]:
        return nullcontext()

    def get(self, _model: type[BitbucketConnection], _key: int) -> BitbucketConnection:
        return self.connection


@pytest.fixture(scope="module")
def bitbucket_api_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for the focused OAuth API."""
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


def oauth_settings() -> Settings:
    return Settings(
        jwt_secret_key=SecretStr(SIGNING_SECRET),
        bitbucket_oauth_client_id="verboflex-api-client",
        bitbucket_oauth_client_secret=SecretStr("backend-client-secret"),
        bitbucket_oauth_callback_uri=AnyHttpUrl(CALLBACK_URI),
        bitbucket_oauth_post_callback_path="/admin/bitbucket",
        bitbucket_token_encryption_keyring=SecretStr(FERNET_KEY),
    )


def create_authority(
    factory: sessionmaker[Session],
    *,
    email: str,
    roles: Sequence[str],
) -> tuple[UUID, UUID, str]:
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
    return user_id, auth_session_id, token


def configure_dependencies(
    factory: sessionmaker[Session],
    service: BitbucketOAuthService,
) -> None:
    """Wire principal, OAuth, and route sessions to controlled boundaries."""

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
    params: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        return await client.request(method, path, headers=headers, params=params)


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


def test_admin_oauth_lifecycle_is_state_authoritative_and_locally_revocable(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> None:
    """Complete one callback without ambient bearer authority, then revoke locally."""
    admin_id, admin_session_id, admin_token = create_authority(
        bitbucket_api_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    exchange = FakeTokenExchange()
    redis = FakeRedis()
    service = BitbucketOAuthService(
        settings=oauth_settings(), redis_client=redis, token_exchange=exchange
    )
    configure_dependencies(bitbucket_api_session_factory, service)

    initial = asyncio.run(bitbucket_request("GET", path=BITBUCKET_PATH, access_token=admin_token))
    assert initial.status_code == 200
    assert initial.json() == {
        "status": "Disconnected",
        "scope_profile": "repository",
        "scope_label": "Read-only repository access",
        "connected_at": None,
        "expires_at": None,
        "revoked_at": None,
    }
    assert initial.headers["cache-control"] == "no-store"

    started = asyncio.run(
        bitbucket_request(
            "POST",
            path=f"{BITBUCKET_PATH}/oauth/start",
            access_token=admin_token,
        )
    )
    assert started.status_code == 200
    assert started.headers["cache-control"] == "no-store"
    start_body = started.json()
    assert set(start_body) == {"authorization_url", "state_expires_in"}
    assert start_body["state_expires_in"] == 600
    authorization_url = urlparse(start_body["authorization_url"])
    assert (authorization_url.scheme, authorization_url.netloc, authorization_url.path) == (
        "https",
        "bitbucket.org",
        "/site/oauth2/authorize",
    )
    authorization_query = parse_qs(authorization_url.query)
    assert set(authorization_query) == {"client_id", "response_type", "state"}
    assert authorization_query["client_id"] == ["verboflex-api-client"]
    assert authorization_query["response_type"] == ["code"]
    state = authorization_query["state"][0]
    assert len(state) >= 43

    callback = asyncio.run(
        bitbucket_request(
            "GET",
            path=f"{BITBUCKET_PATH}/oauth/callback",
            params={"state": state, "code": "provider-code"},
        )
    )
    assert callback.status_code == 303
    assert callback.headers["location"] == "/admin/bitbucket"
    assert exchange.calls == [
        {
            "code": "provider-code",
            "callback_uri": CALLBACK_URI,
            "client_id": "verboflex-api-client",
            "client_secret": "backend-client-secret",
        }
    ]
    assert admin_id != admin_session_id

    connected = asyncio.run(bitbucket_request("GET", path=BITBUCKET_PATH, access_token=admin_token))
    assert connected.status_code == 200
    assert connected.json()["status"] == "Connected"
    assert connected.json()["scope_profile"] == "repository"
    assert connected.json()["connected_at"] is not None
    assert connected.json()["expires_at"] is not None
    assert "generation" not in connected.json()

    reconnect = asyncio.run(
        bitbucket_request(
            "POST",
            path=f"{BITBUCKET_PATH}/oauth/reconnect",
            access_token=admin_token,
        )
    )
    reconnect_state = parse_qs(urlparse(reconnect.json()["authorization_url"]).query)["state"][0]
    assert reconnect.status_code == 200
    assert reconnect.headers["cache-control"] == "no-store"

    revoked = asyncio.run(
        bitbucket_request(
            "POST",
            path=f"{BITBUCKET_PATH}/revoke",
            access_token=admin_token,
        )
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "Disconnected"
    assert revoked.json()["revoked_at"] is not None
    assert connection_snapshot(bitbucket_api_session_factory)[0:4] == (
        2,
        None,
        None,
        "repository",
    )
    assert not hasattr(exchange, "revoke_tokens")

    stale_callback = asyncio.run(
        bitbucket_request(
            "GET",
            path=f"{BITBUCKET_PATH}/oauth/callback",
            params={"state": reconnect_state, "code": "stale-code"},
        )
    )
    assert stale_callback.status_code == 400
    assert stale_callback.json() == {"detail": "OAuth callback rejected"}
    assert len(exchange.calls) == 1


def test_every_protected_bitbucket_operation_requires_current_admin_without_mutation(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> None:
    """Deny anonymous and viewer callers before Redis or singleton mutation."""
    _admin_id, _admin_session_id, admin_token = create_authority(
        bitbucket_api_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    _viewer_id, _viewer_session_id, viewer_token = create_authority(
        bitbucket_api_session_factory,
        email="viewer@example.com",
        roles=("viewer",),
    )
    service = BitbucketOAuthService(
        settings=oauth_settings(),
        redis_client=FakeRedis(),
        token_exchange=FakeTokenExchange(),
    )
    configure_dependencies(bitbucket_api_session_factory, service)
    before = connection_snapshot(bitbucket_api_session_factory)

    protected = (
        ("GET", BITBUCKET_PATH),
        ("POST", f"{BITBUCKET_PATH}/oauth/start"),
        ("POST", f"{BITBUCKET_PATH}/oauth/reconnect"),
        ("POST", f"{BITBUCKET_PATH}/revoke"),
    )
    for method, path in protected:
        anonymous = asyncio.run(bitbucket_request(method, path=path))
        viewer = asyncio.run(bitbucket_request(method, path=path, access_token=viewer_token))
        assert anonymous.status_code == 401
        assert viewer.status_code == 403

    assert connection_snapshot(bitbucket_api_session_factory) == before
    assert (
        asyncio.run(
            bitbucket_request("GET", path=BITBUCKET_PATH, access_token=admin_token)
        ).status_code
        == 200
    )


def test_callback_rejects_hostile_state_without_bearer_or_provider_diagnostics(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> None:
    """Keep callback errors bounded and consume authority only from valid state."""
    exchange = FakeTokenExchange()
    service = BitbucketOAuthService(
        settings=oauth_settings(), redis_client=FakeRedis(), token_exchange=exchange
    )
    configure_dependencies(bitbucket_api_session_factory, service)

    rejected = asyncio.run(
        bitbucket_request(
            "GET",
            path=f"{BITBUCKET_PATH}/oauth/callback",
            params={"state": "forged", "code": "hostile"},
        )
    )
    assert rejected.status_code == 400
    assert rejected.json() == {"detail": "OAuth callback rejected"}
    assert rejected.headers["cache-control"] == "no-store"
    assert exchange.calls == []
    assert "provider" not in rejected.text.casefold()


def test_public_status_fails_closed_for_structurally_incomplete_credentials() -> None:
    """Keep the read model unavailable if durable pair integrity is ever bypassed."""
    connection = BitbucketConnection(
        id=1,
        access_token_ciphertext=b"encrypted-access",
        refresh_token_ciphertext=None,
    )
    service = BitbucketOAuthService(
        settings=oauth_settings(), redis_client=FakeRedis(), token_exchange=FakeTokenExchange()
    )

    snapshot = service.public_status(cast(Session, FakeStatusSession(connection)))

    assert snapshot.state == "unavailable"


def test_missing_configuration_and_missing_principal_session_fail_closed(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> None:
    """Project bounded unavailable state instead of constructing partial authority."""
    _admin_id, _admin_session_id, admin_token = create_authority(
        bitbucket_api_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )

    def override_session() -> Generator[Session]:
        with bitbucket_api_session_factory() as session:
            yield session

    incomplete = Settings(jwt_secret_key=SecretStr(SIGNING_SECRET))
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = lambda: incomplete

    unavailable = asyncio.run(
        bitbucket_request("GET", path=BITBUCKET_PATH, access_token=admin_token)
    )
    assert unavailable.status_code == 200
    assert unavailable.json()["status"] == "Unavailable"
    assert unavailable.headers["cache-control"] == "no-store"

    rejected_start = asyncio.run(
        bitbucket_request(
            "POST",
            path=f"{BITBUCKET_PATH}/oauth/start",
            access_token=admin_token,
        )
    )
    assert rejected_start.status_code == 503
    assert rejected_start.json() == {"detail": "Bitbucket connection unavailable"}
    assert rejected_start.headers["cache-control"] == "no-store"

    principal_without_session = Principal(
        user_id=uuid4(),
        email="admin@example.com",
        display_name="Admin",
        roles=(RoleName.ADMIN,),
        must_change_password=False,
    )
    with pytest.raises(HTTPException) as missing_session:
        _session_id(principal_without_session)
    assert missing_session.value.status_code == 503


def test_missing_singleton_and_wrong_callback_destination_are_bounded(
    bitbucket_api_session_factory: sessionmaker[Session],
) -> None:
    """Reject missing durable authority and fixed-destination drift without exchange."""
    admin_id, admin_session_id, admin_token = create_authority(
        bitbucket_api_session_factory,
        email="admin@example.com",
        roles=("admin",),
    )
    exchange = FakeTokenExchange()
    service = BitbucketOAuthService(
        settings=oauth_settings(), redis_client=FakeRedis(), token_exchange=exchange
    )
    configure_dependencies(bitbucket_api_session_factory, service)
    state = service.start(
        admin_id=admin_id,
        session_id=admin_session_id,
        expected_generation=0,
    )
    with bitbucket_api_session_factory.begin() as session:
        session.execute(text("DELETE FROM bitbucket_connections"))

    with bitbucket_api_session_factory() as session:
        assert service.public_status(session).state == "unavailable"
    with bitbucket_api_session_factory() as session, pytest.raises(OAuthConnectionUnavailable):
        service.start_current(
            session,
            admin_id=admin_id,
            session_id=admin_session_id,
        )

    missing_callback = asyncio.run(
        bitbucket_request(
            "GET",
            path=f"{BITBUCKET_PATH}/oauth/callback",
            params={"state": state, "code": "provider-code"},
        )
    )
    assert missing_callback.status_code == 503
    assert missing_callback.json() == {"detail": "Bitbucket connection unavailable"}
    assert missing_callback.headers["cache-control"] == "no-store"
    assert exchange.calls == []

    with bitbucket_api_session_factory.begin() as session:
        session.add(BitbucketConnection(id=1))
    wrong_destination_state = service.start(
        admin_id=admin_id,
        session_id=admin_session_id,
        expected_generation=0,
    )
    with (
        bitbucket_api_session_factory() as session,
        pytest.raises(OAuthCallbackRejected, match="OAuth callback rejected"),
    ):
        service.complete_callback_from_state(
            session,
            state=wrong_destination_state,
            code="provider-code",
            callback_uri=CALLBACK_URI,
            post_callback_path="/attacker",
        )
    assert exchange.calls == []
    assert (
        asyncio.run(
            bitbucket_request("GET", path=BITBUCKET_PATH, access_token=admin_token)
        ).status_code
        == 200
    )


def test_standard_library_token_exchange_is_bounded_exact_and_redirect_free() -> None:
    """Send credentials only to the fixed endpoint and bound every response read."""
    response = FakeHTTPResponse(
        b'{"access_token":"a","refresh_token":"r","scope":"repository","expires_in":1}'
    )
    opener = FakeOpener(response=response)
    exchange = BitbucketOAuthTokenExchange(opener=cast(OpenerDirector, opener))

    authorization = exchange.exchange_authorization_code(
        code="code",
        callback_uri=CALLBACK_URI,
        client_id="client",
        client_secret="secret",
    )
    refreshed = exchange.refresh_tokens(
        refresh_token="refresh",
        client_id="client",
        client_secret="secret",
    )
    assert authorization["scope"] == refreshed["scope"] == "repository"
    assert response.read_limits == [MAX_TOKEN_RESPONSE_BYTES + 1] * 2
    assert [timeout for _request, timeout in opener.calls] == [
        TOKEN_EXCHANGE_TIMEOUT_SECONDS,
        TOKEN_EXCHANGE_TIMEOUT_SECONDS,
    ]
    first_request, _timeout = opener.calls[0]
    assert first_request.full_url == "https://bitbucket.org/site/oauth2/access_token"
    assert first_request.method == "POST"
    assert first_request.get_header("Authorization") == "Basic Y2xpZW50OnNlY3JldA=="
    assert first_request.data == (
        b"grant_type=authorization_code&code=code&redirect_uri="
        b"https%3A%2F%2Fapi.verboflex.example%2Fapi%2Fv1%2Fadmin%2Fbitbucket%2Foauth%2Fcallback"
    )

    assert BitbucketOAuthTokenExchange()
    redirect_handler = _RejectRedirects()
    assert (
        redirect_handler.redirect_request(
            Request("https://bitbucket.org/original"),
            BytesIO(),
            302,
            "Found",
            cast(Any, Message()),
            "https://attacker.example/redirect",
        )
        is None
    )


@pytest.mark.parametrize(
    ("payload", "error"),
    (
        (b"x" * (MAX_TOKEN_RESPONSE_BYTES + 1), None),
        (b"not-json", None),
        (b"[]", None),
        (b"", URLError("provider unavailable")),
    ),
)
def test_standard_library_token_exchange_sanitizes_every_failure(
    payload: bytes,
    error: Exception | None,
) -> None:
    """Reject redirects, transport failures, invalid JSON, and oversized bodies alike."""
    opener = FakeOpener(response=FakeHTTPResponse(payload), error=error)
    exchange = BitbucketOAuthTokenExchange(opener=cast(OpenerDirector, opener))

    with pytest.raises(OAuthCallbackRejected) as rejected:
        exchange.exchange_authorization_code(
            code="code",
            callback_uri=CALLBACK_URI,
            client_id="client",
            client_secret="secret",
        )
    assert str(rejected.value) == "OAuth callback rejected"
    assert "provider unavailable" not in str(rejected.value)
