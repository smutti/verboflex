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
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import decode_access_token
from verboflex.auth.passwords import hash_password
from verboflex.auth.rate_limits import get_redis_client
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
        cors_origins=("https://app.verboflex.example",),
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
    ) as client:
        return await client.post("/api/v1/auth/refresh", headers=headers, cookies=cookies)


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
        persisted = session.execute(
            select(AuthSession).order_by(AuthSession.created_at, AuthSession.id)
        ).scalars().all()
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
