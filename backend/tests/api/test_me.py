"""HTTP contracts for the authenticated current-identity projection."""

import asyncio
import os
from collections.abc import Generator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.role import Role
from verboflex.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
SIGNING_SECRET = "0123456789abcdef" * 2
USER_ID = UUID("00000000-0000-4000-8000-000000000101")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000201")


@pytest.fixture
def principal_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for principal resolution."""
    database_name = f"verboflex_principal_{uuid4().hex}"
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


def principal_settings() -> Settings:
    """Return explicit signing settings independent from ambient env."""
    return Settings(jwt_secret_key=SIGNING_SECRET, refresh_cookie_secure=False)


def configure_principal_dependencies(factory: sessionmaker[Session]) -> None:
    """Wire the protected route to its isolated PostgreSQL database."""

    def override_session() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = principal_settings


def create_principal_authority(factory: sessionmaker[Session]) -> str:
    """Persist current authority and return its signed ordinary bearer token."""
    with factory.begin() as session:
        roles = session.execute(
            select(Role).where(Role.name.in_(("translator", "admin")))
        ).scalars()
        user = User(
            id=USER_ID,
            email="person@example.com",
            display_name="Person Example",
            hashed_password=hash_password("principal password phrase!"),
            must_change_password=False,
            roles=list(roles),
        )
        session.add(user)
        session.add(
            AuthSession(
                id=SESSION_ID,
                user_id=USER_ID,
                family_id=uuid4(),
                token_hash="f" * 64,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
    return issue_access_token(
        user_id=USER_ID,
        session_id=SESSION_ID,
        token_version=0,
        purpose="access",
        settings=principal_settings(),
    )


async def get_me(access_token: str) -> httpx.Response:
    """Call the registered protected route through the ASGI boundary."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )


def test_current_identity_returns_only_the_safe_provider_independent_projection(
    principal_session_factory: sessionmaker[Session],
) -> None:
    """Return exact own identity and sorted stable roles without persistence fields."""
    access_token = create_principal_authority(principal_session_factory)
    configure_principal_dependencies(principal_session_factory)

    response = asyncio.run(get_me(access_token))

    assert response.status_code == 200
    assert response.json() == {
        "id": "00000000-0000-4000-8000-000000000101",
        "email": "person@example.com",
        "display_name": "Person Example",
        "roles": ["admin", "translator"],
        "must_change_password": False,
    }
