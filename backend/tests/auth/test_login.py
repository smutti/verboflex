"""HTTP contracts for internal corporate-email credential exchange."""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import RedisDsn, SecretStr
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth import login as login_service
from verboflex.auth.access_tokens import decode_access_token
from verboflex.auth.passwords import hash_password
from verboflex.auth.rate_limits import (
    LOGIN_RATE_LIMIT_SCRIPT,
    LOGIN_WINDOW_SECONDS,
    enforce_login_rate_limit,
    get_redis_client,
)
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
SIGNING_SECRET = "0123456789abcdef" * 2
VALID_PASSWORD = "ordinary login phrase!"


@dataclass
class FakeRedis:
    """Deterministic Redis boundary whose calls remain observable."""

    result: object | None = None
    attempts: int = 0
    calls: list[tuple[str, int, tuple[object, ...]]] = field(default_factory=list)

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        """Record one atomic rate-limit invocation."""
        self.calls.append((script, numkeys, keys_and_args))
        if isinstance(self.result, BaseException):
            raise self.result
        if self.result is not None:
            return self.result
        self.attempts += 1
        return [self.attempts, 60]


@pytest.fixture
def login_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated real PostgreSQL database for an HTTP contract."""
    database_name = f"verboflex_login_{uuid4().hex}"
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


def login_settings() -> Settings:
    """Return explicit local auth settings independent from ambient env."""
    return Settings(
        jwt_secret_key=SecretStr(SIGNING_SECRET),
        refresh_cookie_secure=False,
    )


def configure_dependencies(factory: sessionmaker[Session], redis_client: FakeRedis) -> None:
    """Wire the ASGI boundary to isolated PostgreSQL and deterministic Redis."""

    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_redis_client] = lambda: redis_client
    app.dependency_overrides[get_settings] = login_settings


async def post_token(username: str, password: str) -> httpx.Response:
    """Submit the exact OAuth2 form through the ASGI transport."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1",
    ) as client:
        return await client.post(
            "/api/v1/auth/token",
            data={"username": username, "password": password},
        )


def create_login_user(
    factory: sessionmaker[Session],
    *,
    email: str = "person@example.com",
    is_active: bool = True,
    must_change_password: bool = False,
) -> User:
    """Persist one internal account through the real database boundary."""
    with factory.begin() as session:
        user = User(
            email=email,
            display_name="Person Example",
            hashed_password=hash_password(VALID_PASSWORD),
            is_active=is_active,
            must_change_password=must_change_password,
        )
        session.add(user)
    return user


def test_ordinary_login_creates_only_hashed_refresh_authority(
    login_session_factory: sessionmaker[Session],
) -> None:
    """Exchange normalized credentials for bearer and hashed seven-day session."""
    user = create_login_user(login_session_factory)
    redis_client = FakeRedis()
    configure_dependencies(login_session_factory, redis_client)

    response = asyncio.run(post_token(" \tPERSON@EXAMPLE.COM\r ", VALID_PASSWORD))

    assert response.status_code == 200
    assert response.json() == {
        "access_token": response.json()["access_token"],
        "token_type": "bearer",
        "expires_in": 900,
        "must_change_password": False,
    }
    refresh_token = response.cookies["__Secure-verboflex_refresh"]
    set_cookie = response.headers["set-cookie"]
    assert "__Secure-verboflex_refresh=" in set_cookie
    assert "verboflex_refresh=" not in set_cookie.replace(
        "__Secure-verboflex_refresh=", ""
    )
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie

    with login_session_factory() as session:
        persisted = session.execute(select(AuthSession)).scalar_one()
    assert persisted.user_id == user.id
    assert persisted.token_hash == hashlib.sha256(refresh_token.encode()).hexdigest()
    assert persisted.token_hash != refresh_token
    assert persisted.used_at is None
    assert persisted.revoked_at is None
    remaining = persisted.expires_at - datetime.now(UTC)
    assert 604_790 <= remaining.total_seconds() <= 604_800

    claims = decode_access_token(
        response.json()["access_token"],
        settings=login_settings(),
    )
    assert claims.user_id == user.id
    assert claims.session_id == persisted.id
    assert redis_client.calls


def test_temporary_login_creates_only_password_change_authority(
    login_session_factory: sessionmaker[Session],
) -> None:
    """Return five-minute restricted authority without refresh persistence."""
    user = create_login_user(login_session_factory, must_change_password=True)
    redis_client = FakeRedis()
    configure_dependencies(login_session_factory, redis_client)

    response = asyncio.run(post_token("person@example.com", VALID_PASSWORD))

    assert response.status_code == 200
    assert response.json() == {
        "access_token": response.json()["access_token"],
        "token_type": "bearer",
        "expires_in": 300,
        "must_change_password": True,
    }
    assert "verboflex_refresh" not in response.cookies
    assert "set-cookie" not in response.headers
    with login_session_factory() as session:
        assert session.execute(select(AuthSession)).scalars().all() == []

    claims = decode_access_token(
        response.json()["access_token"],
        settings=login_settings(),
        expected_purpose="password_change",
    )
    assert claims.user_id == user.id
    assert claims.session_id is None


def test_ordinary_login_requests_exact_refresh_token_entropy(
    login_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Request 32 random bytes for the opaque refresh credential."""
    create_login_user(login_session_factory)
    requested_bytes: list[int | None] = []

    def deterministic_token(nbytes: int | None = None) -> str:
        requested_bytes.append(nbytes)
        return "opaque-refresh-token-for-entropy-contract"

    monkeypatch.setattr("verboflex.auth.login.secrets.token_urlsafe", deterministic_token)
    configure_dependencies(login_session_factory, FakeRedis())

    response = asyncio.run(post_token("person@example.com", VALID_PASSWORD))

    assert response.status_code == 200
    assert requested_bytes == [32]
    with login_session_factory() as session:
        persisted = session.execute(select(AuthSession)).scalar_one()
    assert (
        persisted.token_hash
        == hashlib.sha256(response.cookies["verboflex_refresh"].encode()).hexdigest()
    )


def test_malformed_identifier_uses_canonical_limit_key_without_a_user_query(
    login_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rate-limit malformed identifiers consistently while preserving the dummy path."""
    redis_client = FakeRedis()
    configure_dependencies(login_session_factory, redis_client)

    def forbidden_query(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("malformed identifiers must not reach the user query")

    monkeypatch.setattr(Session, "execute", forbidden_query)

    response = asyncio.run(post_token(" \tNOT AN EMAIL\r ", VALID_PASSWORD))

    normalized_email = "not an email"
    identity_digest = hashlib.sha256(
        f"{normalized_email}\0{httpx.URL('http://127.0.0.1').host}".encode()
    ).hexdigest()
    assert response.status_code == 401
    assert redis_client.calls == [
        (
            LOGIN_RATE_LIMIT_SCRIPT,
            1,
            (f"verboflex:auth:login:{identity_digest}", str(LOGIN_WINDOW_SECONDS)),
        )
    ]


def test_malformed_identifier_fallback_strips_only_approved_ascii_whitespace(
    login_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Do not let Python's broader Unicode whitespace set rewrite limiter identity."""
    observed_identifiers: list[str] = []

    def observe_limit(
        _redis_client: object,
        *,
        normalized_email: str,
        client_ip: str,
    ) -> object:
        del client_ip
        observed_identifiers.append(normalized_email)
        return type("Allowed", (), {"allowed": True, "retry_after": 0})()

    monkeypatch.setattr(login_service, "enforce_login_rate_limit", observe_limit)
    with (
        login_session_factory() as session,
        pytest.raises(login_service.InvalidCredentials) as error,
    ):
        login_service.authenticate_login(
            session,
            FakeRedis(),
            email="\N{NO-BREAK SPACE}NOT AN EMAIL\N{NO-BREAK SPACE}",
            password=VALID_PASSWORD,
            client_ip="192.0.2.10",
            settings=login_settings(),
        )

    assert observed_identifiers == ["\N{NO-BREAK SPACE}not an email\N{NO-BREAK SPACE}"]
    assert error.value.args == (login_service.INVALID_CREDENTIALS_MESSAGE,)


def test_login_rate_limit_exception_preserves_exact_internal_semantics() -> None:
    """Keep the retry metadata paired with one stable internal exhaustion reason."""
    error = login_service.LoginRateLimited(23)

    assert error.args == (login_service.LOGIN_RATE_LIMITED_MESSAGE,)
    assert error.retry_after == 23


def test_ordinary_login_binds_access_claims_to_the_session_creation_clock(
    login_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use one UTC instant for refresh expiry and ordinary bearer issuance."""
    create_login_user(login_session_factory)
    observed_now: list[datetime | None] = []

    def observe_issue_access_token(**kwargs: object) -> str:
        observed_now.append(kwargs.get("now"))
        return "observed-access-token"

    monkeypatch.setattr(login_service, "issue_access_token", observe_issue_access_token)
    with login_session_factory() as session:
        authority = login_service.authenticate_login(
            session,
            FakeRedis(),
            email="person@example.com",
            password=VALID_PASSWORD,
            client_ip="192.0.2.10",
            settings=login_settings(),
        )
    with login_session_factory() as session:
        persisted = session.execute(select(AuthSession)).scalar_one()

    assert authority.access_token == "observed-access-token"
    assert len(observed_now) == 1
    assert observed_now[0] is not None
    assert observed_now[0].tzinfo == UTC
    assert persisted.expires_at == observed_now[0] + timedelta(
        days=login_settings().refresh_token_expire_days
    )


@pytest.mark.parametrize(
    ("scenario", "submitted_email", "submitted_password", "is_active"),
    [
        ("wrong password", "person@example.com", "wrong password phrase!", True),
        ("unknown email", "unknown@example.com", VALID_PASSWORD, True),
        ("malformed email", " \tNOT AN EMAIL\r ", VALID_PASSWORD, True),
        ("inactive account", "person@example.com", VALID_PASSWORD, False),
    ],
)
def test_invalid_unknown_and_inactive_credentials_are_indistinguishable(
    login_session_factory: sessionmaker[Session],
    scenario: str,
    submitted_email: str,
    submitted_password: str,
    is_active: bool,
) -> None:
    """Return one stable 401 surface and create no authority in every case."""
    create_login_user(login_session_factory, is_active=is_active)
    configure_dependencies(login_session_factory, FakeRedis())

    response = asyncio.run(post_token(submitted_email, submitted_password))

    assert response.status_code == 401, scenario
    assert response.json() == {"detail": "Invalid credentials"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert "set-cookie" not in response.headers
    with login_session_factory() as session:
        assert session.execute(select(AuthSession)).scalars().all() == []


def test_unknown_email_traverses_the_dummy_argon2_verification_path(
    login_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown accounts still pay one password-verification path without authority."""
    observed_hashes: list[str] = []

    def observe_verification(_password: str, password_hash: str) -> bool:
        observed_hashes.append(password_hash)
        return False

    monkeypatch.setattr(login_service, "verify_password", observe_verification)
    configure_dependencies(login_session_factory, FakeRedis())

    response = asyncio.run(post_token("unknown@example.com", VALID_PASSWORD))

    assert response.status_code == 401
    assert len(observed_hashes) == 1
    assert observed_hashes[0].startswith("$argon2")


def test_sixth_login_attempt_is_limited_before_password_verification(
    login_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return exact 429 metadata before a sixth password hash is evaluated."""
    create_login_user(login_session_factory)
    redis_client = FakeRedis()
    verification_calls = 0

    def reject_password(_password: str, _password_hash: str) -> bool:
        nonlocal verification_calls
        verification_calls += 1
        return False

    monkeypatch.setattr(login_service, "verify_password", reject_password)
    configure_dependencies(login_session_factory, redis_client)

    responses = [
        asyncio.run(post_token("person@example.com", "wrong password phrase!")) for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [401, 401, 401, 401, 401, 429]
    assert responses[-1].json() == {"detail": "Rate limit exceeded"}
    assert int(responses[-1].headers["retry-after"]) > 0
    assert responses[-1].headers["x-ratelimit-remaining"] == "0"
    assert verification_calls == 5
    with login_session_factory() as session:
        assert session.execute(select(AuthSession)).scalars().all() == []


def test_redis_outage_fails_closed_before_verification_or_mutation(
    login_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return exact 503 without touching Argon2 or durable session state."""
    create_login_user(login_session_factory)

    def forbidden_verification(_password: str, _password_hash: str) -> bool:
        raise AssertionError("password verification must not run during Redis outage")

    monkeypatch.setattr(login_service, "verify_password", forbidden_verification)
    configure_dependencies(
        login_session_factory,
        FakeRedis(result=RedisConnectionError("redis unavailable")),
    )

    response = asyncio.run(post_token("person@example.com", VALID_PASSWORD))

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service unavailable"}
    assert "set-cookie" not in response.headers
    with login_session_factory() as session:
        assert session.execute(select(AuthSession)).scalars().all() == []


@pytest.mark.parametrize("invalid_state", [[], [1], ["not-an-integer", 60]])
def test_invalid_redis_limiter_state_fails_closed(
    login_session_factory: sessionmaker[Session],
    invalid_state: object,
) -> None:
    """Treat malformed Redis results as an unavailable authentication service."""
    configure_dependencies(login_session_factory, FakeRedis(result=invalid_state))

    response = asyncio.run(post_token("person@example.com", VALID_PASSWORD))

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service unavailable"}


def test_redis_dependency_uses_the_configured_database_url() -> None:
    """Build the request-scoped limiter client from the explicit Redis setting."""
    settings = Settings(
        jwt_secret_key=SecretStr(SIGNING_SECRET),
        redis_url=RedisDsn("redis://127.0.0.1:6380/4"),
        refresh_cookie_secure=False,
    )

    client = get_redis_client(settings)

    assert client.connection_pool.connection_kwargs["host"] == "127.0.0.1"
    assert client.connection_pool.connection_kwargs["port"] == 6380
    assert client.connection_pool.connection_kwargs["db"] == 4
    assert client.connection_pool.connection_kwargs["decode_responses"] is True


@pytest.mark.parametrize(
    ("raw_state", "expected_allowed", "expected_remaining", "expected_retry_after"),
    [([3, 42], True, 2, 42), ([6, 0], False, 0, 1)],
)
def test_rate_limiter_uses_one_exact_atomic_redis_contract(
    raw_state: list[int],
    expected_allowed: bool,
    expected_remaining: int,
    expected_retry_after: int,
) -> None:
    """Bind the fixed-window result and privacy-preserving Redis key exactly."""
    redis_client = FakeRedis(result=raw_state)

    result = enforce_login_rate_limit(
        redis_client,
        normalized_email="person@example.com",
        client_ip="192.0.2.42",
    )

    digest = hashlib.sha256(b"person@example.com\x00192.0.2.42").hexdigest()
    assert redis_client.calls == [
        (
            LOGIN_RATE_LIMIT_SCRIPT,
            1,
            (f"verboflex:auth:login:{digest}", str(LOGIN_WINDOW_SECONDS)),
        )
    ]
    assert result.allowed is expected_allowed
    assert result.remaining == expected_remaining
    assert result.retry_after == expected_retry_after
