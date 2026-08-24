"""HTTP contracts for internal corporate-email credential exchange."""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.api.v1.routes.auth import get_redis_client
from verboflex.auth import login as login_service
from verboflex.auth.access_tokens import decode_access_token
from verboflex.auth.passwords import hash_password
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
        jwt_secret_key=SIGNING_SECRET,
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
    refresh_token = response.cookies["verboflex_refresh"]
    set_cookie = response.headers["set-cookie"]
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


@pytest.mark.parametrize(
    ("scenario", "submitted_email", "submitted_password", "is_active"),
    [
        ("wrong password", "person@example.com", "wrong password phrase!", True),
        ("unknown email", "unknown@example.com", VALID_PASSWORD, True),
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
        asyncio.run(post_token("person@example.com", "wrong password phrase!"))
        for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [401, 401, 401, 401, 401, 429]
    assert responses[-1].json() == {"detail": "Rate limit exceeded"}
    assert int(responses[-1].headers["retry-after"]) > 0
    assert responses[-1].headers["x-ratelimit-remaining"] == "0"
    assert verification_calls == 5
    with login_session_factory() as session:
        assert session.execute(select(AuthSession)).scalars().all() == []
