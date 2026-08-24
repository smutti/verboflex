"""HTTP contracts for rotating refresh-session authority."""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import AnyHttpUrl, SecretStr
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import decode_access_token
from verboflex.auth.passwords import hash_password
from verboflex.auth.rate_limits import (
    LOGIN_RATE_LIMIT_SCRIPT,
    enforce_auth_action_rate_limit,
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
REFRESH_TOKEN = "A" * 43
USER_ID = UUID("00000000-0000-4000-8000-000000000701")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000702")
FAMILY_ID = UUID("00000000-0000-4000-8000-000000000703")


@dataclass
class FakeRedis:
    """Deterministic Redis boundary with observable fixed-window calls."""

    result: object = field(default_factory=lambda: [1, 60])
    calls: list[tuple[str, int, tuple[object, ...]]] = field(default_factory=list)

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        """Record and return one limiter result."""
        self.calls.append((script, numkeys, keys_and_args))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


@pytest.fixture
def refresh_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated real PostgreSQL database for refresh contracts."""
    database_name = f"verboflex_refresh_{uuid4().hex}"
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


def refresh_settings() -> Settings:
    """Return explicit local settings with one exact allowed browser origin."""
    return Settings(
        jwt_secret_key=SecretStr(SIGNING_SECRET),
        refresh_cookie_secure=False,
        cors_origins=(AnyHttpUrl("https://app.verboflex.example"),),
    )


def configure_dependencies(
    factory: sessionmaker[Session], redis_client: FakeRedis | None = None
) -> FakeRedis:
    """Wire refresh requests to isolated PostgreSQL and deterministic Redis."""
    client = redis_client or FakeRedis()

    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_redis_client] = lambda: client
    app.dependency_overrides[get_settings] = refresh_settings
    return client


def test_sensitive_action_limiter_hashes_authority_and_preserves_exact_window_state() -> None:
    """Prove the Redis key, script arguments, inclusive limit, and TTL floor."""
    redis_client = FakeRedis(result=[30, 0])

    result = enforce_auth_action_rate_limit(
        redis_client,
        action="refresh",
        identity=REFRESH_TOKEN,
        client_ip="192.0.2.10",
        limit=30,
    )

    expected_digest = hashlib.sha256((f"{REFRESH_TOKEN}\0" + "192.0.2.10").encode()).hexdigest()
    assert redis_client.calls == [
        (
            LOGIN_RATE_LIMIT_SCRIPT,
            1,
            (f"verboflex:auth:refresh:{expected_digest}", "60"),
        )
    ]
    assert REFRESH_TOKEN not in redis_client.calls[0][2][0]
    assert "192.0.2.10" not in redis_client.calls[0][2][0]
    assert result.allowed is True
    assert result.remaining == 0
    assert result.retry_after == 1


def create_refresh_authority(factory: sessionmaker[Session]) -> AuthSession:
    """Persist one valid ordinary refresh session with hashed token material."""
    auth_session = AuthSession(
        id=SESSION_ID,
        user_id=USER_ID,
        family_id=FAMILY_ID,
        token_hash=hashlib.sha256(REFRESH_TOKEN.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    with factory.begin() as session:
        session.add(
            User(
                id=USER_ID,
                email="person@example.com",
                display_name="Person Example",
                hashed_password=hash_password("ordinary login phrase!"),
                must_change_password=False,
            )
        )
        session.add(auth_session)
    return auth_session


async def post_refresh(
    token: str | None = REFRESH_TOKEN,
    *,
    origin: str | None = "https://app.verboflex.example",
) -> httpx.Response:
    """Call the registered refresh route with ambient cookie authority."""
    headers = {"Origin": origin} if origin is not None else {}
    cookies = {"verboflex_refresh": token} if token is not None else None
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1",
        cookies=cookies,
    ) as client:
        return await client.post("/api/v1/auth/refresh", headers=headers)


def test_valid_refresh_rotates_once_and_returns_new_authority(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Rotate one hash into a distinct cookie and 900-second access token."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory)

    response = asyncio.run(post_refresh())

    assert response.status_code == 200
    assert response.json() == {
        "access_token": response.json()["access_token"],
        "token_type": "bearer",
        "expires_in": 900,
        "must_change_password": False,
    }
    successor_token = response.cookies["verboflex_refresh"]
    assert successor_token != REFRESH_TOKEN
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "Path=/api/v1/auth" in response.headers["set-cookie"]

    with refresh_session_factory() as session:
        persisted = (
            session.execute(select(AuthSession).order_by(AuthSession.created_at, AuthSession.id))
            .scalars()
            .all()
        )
    assert len(persisted) == 2
    predecessor = next(item for item in persisted if item.id == SESSION_ID)
    successor = next(item for item in persisted if item.id != SESSION_ID)
    assert predecessor.used_at is not None
    assert predecessor.revoked_at is None
    assert successor.parent_id == predecessor.id
    assert successor.family_id == FAMILY_ID
    assert successor.token_hash == hashlib.sha256(successor_token.encode()).hexdigest()
    assert successor.token_hash != successor_token
    assert successor.used_at is None
    assert successor.revoked_at is None
    claims = decode_access_token(response.json()["access_token"], settings=refresh_settings())
    assert claims.session_id == successor.id
    assert claims.user_id == USER_ID


def test_refresh_successor_uses_the_exact_rotation_timeline(
    refresh_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bind both successor expiry and access claims to the serialized rotation instant."""
    create_refresh_authority(refresh_session_factory)
    rotated_at = (datetime.now(UTC) - timedelta(minutes=1)).replace(microsecond=0)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, timezone: object = None) -> FrozenDateTime:
            return cls.fromtimestamp(rotated_at.timestamp(), UTC)

    monkeypatch.setattr("verboflex.auth.refresh_sessions.datetime", FrozenDateTime)
    configure_dependencies(refresh_session_factory)

    response = asyncio.run(post_refresh())

    assert response.status_code == 200
    claims = decode_access_token(response.json()["access_token"], settings=refresh_settings())
    assert claims.issued_at == rotated_at
    with refresh_session_factory() as session:
        successor = session.execute(
            select(AuthSession).where(AuthSession.parent_id == SESSION_ID)
        ).scalar_one()
    assert successor.expires_at == rotated_at + timedelta(
        days=refresh_settings().refresh_token_expire_days
    )


@pytest.mark.parametrize("origin", [None, "https://app.verboflex.example"])
def test_absent_or_exact_allowed_origin_can_rotate(
    refresh_session_factory: sessionmaker[Session], origin: str | None
) -> None:
    """Accept non-browser callers and the one exact configured browser origin."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory)

    response = asyncio.run(post_refresh(origin=origin))

    assert response.status_code == 200


@pytest.mark.parametrize(
    "session_state",
    ["expired", "revoked"],
)
def test_expired_or_revoked_refresh_returns_exact_401_without_successor(
    refresh_session_factory: sessionmaker[Session], session_state: str
) -> None:
    """Reject dead durable authority without creating another family member."""
    create_refresh_authority(refresh_session_factory)
    with refresh_session_factory.begin() as session:
        auth_session = session.get_one(AuthSession, SESSION_ID)
        if session_state == "expired":
            auth_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        else:
            auth_session.revoked_at = datetime.now(UTC)
    configure_dependencies(refresh_session_factory)

    response = asyncio.run(post_refresh())

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh session"}
    assert "set-cookie" not in response.headers
    with refresh_session_factory() as session:
        persisted = session.execute(select(AuthSession)).scalars().all()
    assert len(persisted) == 1
    assert persisted[0].used_at is None


def test_refresh_is_invalid_at_its_exact_expiry_boundary(
    refresh_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject a refresh session at, not only after, its durable expiry."""
    create_refresh_authority(refresh_session_factory)
    exact_expiry = datetime.now(UTC).replace(microsecond=0)
    with refresh_session_factory.begin() as session:
        session.get_one(AuthSession, SESSION_ID).expires_at = exact_expiry

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, timezone: object = None) -> FrozenDateTime:
            return cls.fromtimestamp(exact_expiry.timestamp(), UTC)

    monkeypatch.setattr("verboflex.auth.refresh_sessions.datetime", FrozenDateTime)
    configure_dependencies(refresh_session_factory)

    response = asyncio.run(post_refresh())

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh session"}
    with refresh_session_factory() as session:
        assert session.execute(select(AuthSession)).scalars().all()[0].used_at is None


@pytest.mark.parametrize("token", [None, "", "not-base64url", "A" * 42, "A" * 44])
def test_missing_or_malformed_refresh_returns_exact_401_without_database_mutation(
    refresh_session_factory: sessionmaker[Session], token: str | None
) -> None:
    """Reject absent and structurally malformed cookies through one stable surface."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory)

    response = asyncio.run(post_refresh(token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh session"}
    assert "set-cookie" not in response.headers
    with refresh_session_factory() as session:
        persisted = session.get_one(AuthSession, SESSION_ID)
    assert persisted.used_at is None
    assert persisted.revoked_at is None


def test_unknown_well_formed_refresh_returns_exact_401_without_database_mutation(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Reject a 256-bit-shaped token whose hash has no durable session."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory)

    response = asyncio.run(post_refresh("C" * 43))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh session"}
    with refresh_session_factory() as session:
        persisted = session.get_one(AuthSession, SESSION_ID)
    assert persisted.used_at is None
    assert persisted.revoked_at is None


@pytest.mark.parametrize("user_state", ["inactive", "password-change-required"])
def test_refresh_rejects_user_without_current_ordinary_authority(
    refresh_session_factory: sessionmaker[Session], user_state: str
) -> None:
    """Reconcile the refresh holder with current user active/password policy."""
    create_refresh_authority(refresh_session_factory)
    with refresh_session_factory.begin() as session:
        user = session.get_one(User, USER_ID)
        if user_state == "inactive":
            user.is_active = False
        else:
            user.must_change_password = True
    configure_dependencies(refresh_session_factory)

    response = asyncio.run(post_refresh())

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh session"}
    with refresh_session_factory() as session:
        persisted = session.get_one(AuthSession, SESSION_ID)
    assert persisted.used_at is None
    assert persisted.revoked_at is None


def test_replayed_predecessor_revokes_every_session_in_its_family(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Treat reuse of consumed authority as theft and revoke its successor."""
    predecessor = create_refresh_authority(refresh_session_factory)
    successor = AuthSession(
        user_id=USER_ID,
        family_id=FAMILY_ID,
        parent_id=SESSION_ID,
        token_hash="b" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    with refresh_session_factory.begin() as session:
        session.get_one(AuthSession, SESSION_ID).used_at = datetime.now(UTC)
        session.add(successor)
    configure_dependencies(refresh_session_factory)

    response = asyncio.run(post_refresh())

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh session"}
    assert "set-cookie" not in response.headers
    with refresh_session_factory() as session:
        family = (
            session.execute(
                select(AuthSession).where(AuthSession.family_id == predecessor.family_id)
            )
            .scalars()
            .all()
        )
    assert len(family) == 2
    assert all(item.revoked_at is not None for item in family)


def test_hostile_origin_is_rejected_before_redis_or_postgresql_mutation(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Reject ambient-cookie CSRF before touching limiter or durable authority."""
    create_refresh_authority(refresh_session_factory)
    redis_client = configure_dependencies(refresh_session_factory)

    response = asyncio.run(post_refresh(origin="https://attacker.example"))

    assert response.status_code == 403
    assert response.json() == {"detail": "Origin not allowed"}
    assert redis_client.calls == []
    with refresh_session_factory() as session:
        persisted = session.get_one(AuthSession, SESSION_ID)
    assert persisted.used_at is None
    assert persisted.revoked_at is None


def test_request_thirty_one_is_limited_before_rotation(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Return exact 429 metadata before the over-limit request reaches PostgreSQL."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory, FakeRedis(result=[31, 47]))

    response = asyncio.run(post_refresh())

    assert response.status_code == 429
    assert response.json() == {"detail": "Rate limit exceeded"}
    assert response.headers["retry-after"] == "47"
    assert response.headers["x-ratelimit-remaining"] == "0"
    with refresh_session_factory() as session:
        persisted = session.get_one(AuthSession, SESSION_ID)
    assert persisted.used_at is None


def test_redis_outage_fails_closed_before_refresh_mutation(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Return exact 503 when authoritative limiting is unavailable."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(
        refresh_session_factory,
        FakeRedis(result=RedisConnectionError("redis unavailable")),
    )

    response = asyncio.run(post_refresh())

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service unavailable"}
    assert "set-cookie" not in response.headers
    with refresh_session_factory() as session:
        persisted = session.get_one(AuthSession, SESSION_ID)
    assert persisted.used_at is None
    assert persisted.revoked_at is None


@pytest.mark.parametrize("invalid_state", [[], [1], ["not-an-integer", 60]])
def test_malformed_refresh_limiter_state_fails_closed(
    refresh_session_factory: sessionmaker[Session], invalid_state: object
) -> None:
    """Treat incomplete or non-numeric Redis results as unavailable authority."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory, FakeRedis(result=invalid_state))

    response = asyncio.run(post_refresh())

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service unavailable"}
    with refresh_session_factory() as session:
        assert session.get_one(AuthSession, SESSION_ID).used_at is None


def test_refresh_requests_exact_32_byte_token_entropy(
    refresh_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Require 256 random bits when creating the replacement cookie."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory)
    requested_bytes: list[int | None] = []

    def deterministic_token(nbytes: int | None = None) -> str:
        requested_bytes.append(nbytes)
        return "B" * 43

    monkeypatch.setattr(
        "verboflex.auth.refresh_sessions.secrets.token_urlsafe",
        deterministic_token,
    )

    response = asyncio.run(post_refresh())

    assert response.status_code == 200
    assert requested_bytes == [32]
    assert response.cookies["verboflex_refresh"] == "B" * 43
