"""Provider-mocked contracts for the Bitbucket client-credentials authority."""

from __future__ import annotations

import base64
import inspect as python_inspect
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any, cast
from urllib.error import URLError
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.core.config import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
ADMIN_ID = UUID("00000000-0000-4000-8000-000000000901")
FERNET_KEY = base64.urlsafe_b64encode(b"0" * 32).decode()
ACCESS_TOKEN = "provider-access-token-must-never-leak"
PROVIDER_ERROR_BODY = "provider-body-must-never-leak"
CLIENT_CREDENTIALS_NOW = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)


@dataclass
class MutableClock:
    """Deterministic provider-authority clock."""

    current: datetime

    def __call__(self) -> datetime:
        return self.current


@dataclass
class FakeTokenExchange:
    """Backend-only provider boundary with observable sanitized calls."""

    client_credentials_calls: list[dict[str, str]] = field(default_factory=list)
    access_token: object = ACCESS_TOKEN
    token_type: object = "bearer"
    scope: object = "repository"
    expires_in: object = 3600
    error: Exception | None = None
    started: Event | None = None
    release: Event | None = None

    def exchange_client_credentials(
        self,
        *,
        client_id: str,
        client_secret: str,
    ) -> dict[str, object]:
        self.client_credentials_calls.append(
            {"client_id": client_id, "client_secret": client_secret}
        )
        if self.started is not None:
            self.started.set()
        if self.release is not None:
            assert self.release.wait(timeout=5)
        if self.error is not None:
            raise self.error
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "scope": self.scope,
            "expires_in": self.expires_in,
            "provider_debug_body": PROVIDER_ERROR_BODY,
        }


@pytest.fixture
def oauth_migration_database() -> Iterator[tuple[Config, Engine]]:
    """Migrate one isolated PostgreSQL database for OAuth persistence."""
    database_name = f"verboflex_oauth_{uuid4().hex}"
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
    try:
        yield config, engine
    finally:
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


@pytest.fixture
def oauth_session_factory(
    oauth_migration_database: tuple[Config, Engine],
) -> Iterator[sessionmaker[Session]]:
    """Expose sessions over the migrated OAuth database."""
    _config, engine = oauth_migration_database
    yield sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def oauth_settings() -> Settings:
    """Return the complete backend-only provider configuration."""
    return Settings(
        bitbucket_oauth_client_id="verboflex-test-client",
        bitbucket_oauth_client_secret=SecretStr("backend-only-client-secret"),
        bitbucket_token_encryption_keyring=SecretStr(FERNET_KEY),
    )


def _connection_snapshot(factory: sessionmaker[Session]) -> tuple[Any, ...]:
    from verboflex.models.bitbucket_connection import BitbucketConnection

    with factory() as session:
        connection = session.execute(select(BitbucketConnection)).scalar_one()
        return (
            connection.generation,
            connection.access_token_ciphertext,
            connection.refresh_token_ciphertext,
            connection.scope_profile,
            connection.provider_expires_at,
            connection.connected_at,
            connection.revoked_at,
        )


def test_client_credentials_persists_access_only_encrypted_generation(
    oauth_session_factory: sessionmaker[Session],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Acquire one exact-scope access-only generation without leaking secrets."""
    from verboflex.models.bitbucket_connection import BitbucketConnection
    from verboflex.security.secret_box import SecretBox
    from verboflex.services.bitbucket_oauth import BitbucketOAuthService

    exchange = FakeTokenExchange()
    service = BitbucketOAuthService(
        settings=oauth_settings(),
        token_exchange=exchange,
        clock=lambda: CLIENT_CREDENTIALS_NOW,
    )

    with oauth_session_factory() as session:
        status = service.acquire_client_credentials(session, actor_id=ADMIN_ID)

    assert status.state == "connected"
    assert status.generation == 1
    assert exchange.client_credentials_calls == [
        {
            "client_id": "verboflex-test-client",
            "client_secret": "backend-only-client-secret",  # pragma: allowlist secret
        }
    ]

    secret_box = SecretBox.from_keyring(FERNET_KEY)
    with oauth_session_factory() as session:
        connection = session.execute(select(BitbucketConnection)).scalar_one()
        assert connection.generation == 1
        assert connection.access_token_ciphertext not in (None, ACCESS_TOKEN)
        assert connection.refresh_token_ciphertext is None
        assert connection.provider_expires_at == CLIENT_CREDENTIALS_NOW.replace(hour=13)
        assert connection.connected_at == CLIENT_CREDENTIALS_NOW
        assert connection.scope_profile == "repository"
        assert secret_box.decrypt(connection.access_token_ciphertext) == ACCESS_TOKEN
        ciphertext = connection.access_token_ciphertext

    for forbidden in (
        ACCESS_TOKEN,
        "backend-only-client-secret",
        FERNET_KEY,
        ciphertext,
    ):
        assert forbidden not in caplog.text


def test_client_credentials_repetition_never_resurrects_generation(
    oauth_session_factory: sessionmaker[Session],
) -> None:
    """Repeated connect, revoke, and reconnect leave only the final generation live."""
    from verboflex.services.bitbucket_oauth import (
        BitbucketOAuthService,
        OAuthGenerationRejected,
    )

    service = BitbucketOAuthService(
        settings=oauth_settings(),
        token_exchange=FakeTokenExchange(),
        clock=lambda: CLIENT_CREDENTIALS_NOW,
    )
    with oauth_session_factory() as session:
        first = service.acquire_client_credentials(session, actor_id=ADMIN_ID)
    with oauth_session_factory() as session:
        first_lease = service.acquire_repository_read_lease(session)
    with oauth_session_factory() as session:
        second = service.acquire_client_credentials(session, actor_id=ADMIN_ID)
    with oauth_session_factory() as session:
        revoked = service.revoke_current(session, actor_id=ADMIN_ID)
    with oauth_session_factory() as session:
        final = service.acquire_client_credentials(session, actor_id=ADMIN_ID)

    assert (first.generation, second.generation, revoked.generation, final.generation) == (
        1,
        2,
        3,
        4,
    )
    with oauth_session_factory() as session, pytest.raises(OAuthGenerationRejected):
        service.require_current_repository_read_lease(session, first_lease)
    with oauth_session_factory() as session:
        final_lease = service.acquire_repository_read_lease(session)
    assert final_lease.generation == 4


def test_client_credentials_rotation_and_revoke_serialize(
    oauth_session_factory: sessionmaker[Session],
) -> None:
    """A revoke waiting on acquisition wins and rejects every stale lease."""
    from verboflex.services.bitbucket_oauth import (
        BitbucketOAuthService,
        OAuthConnectionUnavailable,
    )

    exchange = FakeTokenExchange()
    service = BitbucketOAuthService(
        settings=oauth_settings(),
        token_exchange=exchange,
        clock=lambda: CLIENT_CREDENTIALS_NOW,
    )
    with oauth_session_factory() as session:
        service.acquire_client_credentials(session, actor_id=ADMIN_ID)
    with oauth_session_factory() as session:
        stale_lease = service.acquire_repository_read_lease(session)

    exchange.started = Event()
    exchange.release = Event()

    def rotate() -> Any:
        with oauth_session_factory() as session:
            return service.acquire_client_credentials(session, actor_id=ADMIN_ID)

    def revoke() -> Any:
        with oauth_session_factory() as session:
            return service.revoke_current(session, actor_id=ADMIN_ID)

    with ThreadPoolExecutor(max_workers=2) as executor:
        rotate_future = executor.submit(rotate)
        assert exchange.started.wait(timeout=5)
        revoke_future = executor.submit(revoke)
        exchange.release.set()
        rotated = rotate_future.result(timeout=5)
        revoked = revoke_future.result(timeout=5)

    assert rotated.generation == 2
    assert revoked.generation == 3
    with oauth_session_factory() as session, pytest.raises(OAuthConnectionUnavailable):
        service.require_current_repository_read_lease(session, stale_lease)
    with oauth_session_factory() as session, pytest.raises(OAuthConnectionUnavailable):
        service.acquire_repository_read_lease(session)


def test_client_credentials_expiry_renews_once_for_concurrent_leases(
    oauth_session_factory: sessionmaker[Session],
) -> None:
    """Two callers at exact expiry share one new generation and one exchange."""
    from verboflex.services.bitbucket_oauth import BitbucketOAuthService

    clock = MutableClock(CLIENT_CREDENTIALS_NOW)
    exchange = FakeTokenExchange()
    service = BitbucketOAuthService(
        settings=oauth_settings(),
        token_exchange=exchange,
        clock=clock,
    )
    with oauth_session_factory() as session:
        service.acquire_client_credentials(session, actor_id=ADMIN_ID)

    clock.current = CLIENT_CREDENTIALS_NOW + timedelta(hours=1)
    with oauth_session_factory() as session:
        assert service.public_status(session).state == "reauthorization_required"

    exchange.started = Event()
    exchange.release = Event()

    def acquire_lease() -> Any:
        with oauth_session_factory() as session:
            return service.acquire_repository_read_lease(session)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(acquire_lease)
        assert exchange.started.wait(timeout=5)
        second_future = executor.submit(acquire_lease)
        exchange.release.set()
        first = first_future.result(timeout=5)
        second = second_future.result(timeout=5)

    assert first.generation == second.generation == 2
    assert len(exchange.client_credentials_calls) == 2
    with oauth_session_factory() as session:
        assert service.public_status(session).state == "connected"


def test_client_credentials_renewal_failure_invalidates_expired_generation(
    oauth_session_factory: sessionmaker[Session],
) -> None:
    """Failed or incomplete renewal cannot lease stale expired authority."""
    from verboflex.services.bitbucket_oauth import (
        BitbucketOAuthService,
        OAuthConnectionUnavailable,
    )

    clock = MutableClock(CLIENT_CREDENTIALS_NOW)
    exchange = FakeTokenExchange()
    service = BitbucketOAuthService(
        settings=oauth_settings(),
        token_exchange=exchange,
        clock=clock,
    )
    with oauth_session_factory() as session:
        service.acquire_client_credentials(session, actor_id=ADMIN_ID)
    with oauth_session_factory() as session:
        stale_lease = service.acquire_repository_read_lease(session)

    clock.current += timedelta(hours=1)
    exchange.error = RuntimeError(PROVIDER_ERROR_BODY)
    with oauth_session_factory() as session, pytest.raises(OAuthConnectionUnavailable):
        service.acquire_repository_read_lease(session)
    with oauth_session_factory() as session:
        failed_status = service.public_status(session)
        assert failed_status.state == "reauthorization_required"
        assert set(failed_status.__dataclass_fields__) == {
            "state",
            "connected_at",
            "expires_at",
            "revoked_at",
        }
        with pytest.raises(OAuthConnectionUnavailable):
            service.require_current_repository_read_lease(session, stale_lease)

    snapshot = _connection_snapshot(oauth_session_factory)
    assert snapshot[0] == 2
    assert snapshot[1:3] == (None, None)

    exchange.error = None
    exchange.scope = "repository"
    with oauth_session_factory() as session:
        service.acquire_client_credentials(session, actor_id=ADMIN_ID)
    clock.current += timedelta(hours=1)
    exchange.scope = "repository:write"
    with oauth_session_factory() as session, pytest.raises(OAuthConnectionUnavailable):
        service.acquire_repository_read_lease(session)
    with oauth_session_factory() as session:
        assert service.public_status(session).state == "reauthorization_required"
    snapshot = _connection_snapshot(oauth_session_factory)
    assert snapshot[0] == 4
    assert snapshot[1:3] == (None, None)


def test_client_credentials_expiry_boundary_is_authoritative(
    oauth_session_factory: sessionmaker[Session],
) -> None:
    """The credential is connected just before expiry and rejected at expiry."""
    from verboflex.services.bitbucket_oauth import (
        BitbucketOAuthService,
        OAuthConnectionUnavailable,
    )

    clock = MutableClock(CLIENT_CREDENTIALS_NOW)
    service = BitbucketOAuthService(
        settings=oauth_settings(),
        token_exchange=FakeTokenExchange(),
        clock=clock,
    )
    with oauth_session_factory() as session:
        service.acquire_client_credentials(session)
    clock.current += timedelta(seconds=3599)
    with oauth_session_factory() as session:
        assert service.public_status(session).state == "connected"
    clock.current += timedelta(seconds=1)
    with oauth_session_factory() as session:
        assert service.public_status(session).state == "reauthorization_required"
        with pytest.raises(OAuthConnectionUnavailable):
            service.require_current_repository_read_lease(
                session,
                type("Lease", (), {"generation": 1})(),
            )


def test_client_credentials_malformed_durable_states_and_clock_fail_closed(
    oauth_session_factory: sessionmaker[Session],
) -> None:
    """Missing, legacy, scope-drifted, and naive-time authority never becomes readable."""
    from verboflex.models.bitbucket_connection import BitbucketConnection
    from verboflex.services.bitbucket_oauth import (
        BitbucketCredentialLease,
        BitbucketOAuthService,
        OAuthConnectionUnavailable,
    )

    service = BitbucketOAuthService(
        settings=oauth_settings(),
        token_exchange=FakeTokenExchange(),
        clock=lambda: CLIENT_CREDENTIALS_NOW,
    )
    with oauth_session_factory.begin() as session:
        session.execute(delete(BitbucketConnection))
    with oauth_session_factory() as session:
        assert service.public_status(session).state == "unavailable"
    with (
        oauth_session_factory() as session,
        pytest.raises(OAuthConnectionUnavailable, match="connection unavailable"),
    ):
        service.require_current_repository_read_lease(
            session,
            BitbucketCredentialLease(generation=0, access_token="unused"),
        )

    class StatusSession:
        def __init__(self, connection: object) -> None:
            self.connection = connection

        def begin(self) -> Any:
            return nullcontext()

        def get(self, _model: object, _identity: int) -> object:
            return self.connection

    def connection(**overrides: object) -> object:
        return SimpleNamespace(
            access_token_ciphertext=overrides.get("access_token_ciphertext"),
            refresh_token_ciphertext=overrides.get("refresh_token_ciphertext"),
            scope_profile=overrides.get("scope_profile", "repository"),
            provider_expires_at=overrides.get("provider_expires_at"),
            connected_at=overrides.get("connected_at"),
            revoked_at=overrides.get("revoked_at"),
        )

    malformed_states = (
        (connection(refresh_token_ciphertext="legacy-refresh"), "unavailable"),
        (
            connection(
                access_token_ciphertext="legacy-access",
                refresh_token_ciphertext="legacy-refresh",
                provider_expires_at=CLIENT_CREDENTIALS_NOW + timedelta(hours=1),
            ),
            "reauthorization_required",
        ),
        (
            connection(
                access_token_ciphertext="legacy-access",
                scope_profile="repository:write",
                provider_expires_at=CLIENT_CREDENTIALS_NOW + timedelta(hours=1),
            ),
            "unavailable",
        ),
    )
    for durable_state, expected in malformed_states:
        status_session = cast(Session, StatusSession(durable_state))
        assert service.public_status(status_session).state == expected

    naive_clock_service = BitbucketOAuthService(
        settings=oauth_settings(),
        token_exchange=FakeTokenExchange(),
        clock=lambda: datetime(2026, 8, 29, 12, 0),
    )
    with (
        oauth_session_factory() as session,
        pytest.raises(OAuthConnectionUnavailable, match="connection unavailable"),
    ):
        naive_clock_service.acquire_client_credentials(session)


def test_client_credentials_service_has_no_callback_or_refresh_authority() -> None:
    """Production settings and service own client credentials only."""
    from verboflex.services import bitbucket_oauth

    assert "bitbucket_oauth_callback_uri" not in Settings.model_fields
    assert "bitbucket_oauth_post_callback_path" not in Settings.model_fields
    source = python_inspect.getsource(bitbucket_oauth)
    for forbidden in (
        "RedisOAuthStateClient",
        "OAuthCallbackRejected",
        "exchange_authorization_code",
        "refresh_tokens",
        "complete_callback",
        "authorization_url",
        "oauth-state",
    ):
        assert forbidden not in source


def test_client_credentials_provider_exchange_is_exact_and_bounded() -> None:
    """The adapter sends one exact grant and maps provider details to one error."""
    from verboflex.services.bitbucket_oauth import (
        MAX_TOKEN_RESPONSE_BYTES,
        BitbucketOAuthTokenExchange,
        OAuthConnectionUnavailable,
    )

    class Response:
        def __init__(self, payload: bytes) -> None:
            self.payload = payload

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, amount: int) -> bytes:
            assert amount == MAX_TOKEN_RESPONSE_BYTES + 1
            return self.payload

    class Opener:
        payload = (
            b'{"access_token":"token","token_type":"bearer","scope":"repository","expires_in":3600}'
        )
        request: Any = None
        timeout: int | None = None
        error: Exception | None = None

        def open(self, request: Any, *, timeout: int) -> Response:
            self.request = request
            self.timeout = timeout
            if self.error is not None:
                raise self.error
            return Response(self.payload)

    opener = Opener()
    exchange = BitbucketOAuthTokenExchange(opener=opener)  # type: ignore[arg-type]
    response = exchange.exchange_client_credentials(
        client_id="client-id",
        client_secret="client-secret",  # pragma: allowlist secret
    )
    assert response["scope"] == "repository"
    assert opener.request.full_url == "https://bitbucket.org/site/oauth2/access_token"
    assert opener.request.data == b"grant_type=client_credentials"
    expected = base64.b64encode(b"client-id:client-secret").decode()
    assert opener.request.headers["Authorization"] == f"Basic {expected}"
    assert opener.timeout == 10

    opener.payload = b"x" * (MAX_TOKEN_RESPONSE_BYTES + 1)
    with pytest.raises(OAuthConnectionUnavailable, match="connection unavailable"):
        exchange.exchange_client_credentials(client_id="client-id", client_secret="secret")
    opener.payload = b"not-json"
    with pytest.raises(OAuthConnectionUnavailable, match="connection unavailable"):
        exchange.exchange_client_credentials(client_id="client-id", client_secret="secret")
    opener.payload = b"[]"
    with pytest.raises(OAuthConnectionUnavailable, match="connection unavailable"):
        exchange.exchange_client_credentials(client_id="client-id", client_secret="secret")
    opener.error = URLError(PROVIDER_ERROR_BODY)
    with pytest.raises(OAuthConnectionUnavailable, match="connection unavailable") as failure:
        exchange.exchange_client_credentials(client_id="client-id", client_secret="secret")
    assert PROVIDER_ERROR_BODY not in str(failure.value)


def test_client_credentials_configuration_fails_closed() -> None:
    """Missing provider material and invalid keyrings expose bounded errors only."""
    from verboflex.services.bitbucket_oauth import BitbucketOAuthService

    settings = oauth_settings()
    cases = (
        settings.model_copy(update={"bitbucket_oauth_client_id": None}),
        settings.model_copy(update={"bitbucket_oauth_client_secret": None}),
        settings.model_copy(update={"bitbucket_token_encryption_keyring": None}),
        settings.model_copy(
            update={"bitbucket_token_encryption_keyring": SecretStr("invalid-keyring")}
        ),
    )
    for invalid in cases:
        with pytest.raises(ValueError, match="Bitbucket"):
            BitbucketOAuthService(settings=invalid, token_exchange=FakeTokenExchange())
