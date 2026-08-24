"""PostgreSQL contracts for privileged first-admin and reset operations."""

from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.auth.passwords import verify_password
from verboflex.cli import BootstrapAdminError, bootstrap_first_admin
from verboflex.models.role import Role
from verboflex.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)


@pytest.fixture
def auth_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated database and provide independent transactions."""
    database_name = f"verboflex_bootstrap_{uuid4().hex}"
    with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
        statement = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        admin_connection.execute(statement)

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
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            statement = sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database_name)
            )
            admin_connection.execute(statement)


def test_bootstrap_creates_one_normalized_active_admin_without_a_default(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """Establish one temporary-password admin from explicit secret input."""
    password = "  密碼 phrase 2026!  "
    with auth_session_factory() as session:
        bootstrap_first_admin(
            session,
            email=" \tADMIN@EXAMPLE.COM\r",
            display_name="Admin User",
            password=password,
        )

    with auth_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
        user = session.execute(select(User)).scalar_one()
        assert user.email == "admin@example.com"
        assert user.display_name == "Admin User"
        assert user.is_active is True
        assert user.must_change_password is True
        assert user.token_version == 0
        assert user.hashed_password != password
        assert user.hashed_password.startswith("$argon2")
        assert verify_password(password, user.hashed_password) is True
        assert [role.name for role in user.roles] == ["admin"]


def test_concurrent_bootstrap_attempts_leave_exactly_one_admin(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """Serialize the empty-database decision across independent transactions."""

    def attempt_bootstrap(attempt: int) -> str:
        with auth_session_factory() as session:
            try:
                bootstrap_first_admin(
                    session,
                    email=f"admin{attempt}@example.com",
                    display_name=f"Admin {attempt}",
                    password=f"bootstrap phrase {attempt}!",
                )
            except BootstrapAdminError:
                return "refused"
            return "created"

    with ThreadPoolExecutor(max_workers=4) as executor:
        outcomes = list(executor.map(attempt_bootstrap, range(4)))

    assert outcomes.count("created") == 1
    assert outcomes.count("refused") == 3
    with auth_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
        admin_role = session.execute(select(Role).where(Role.name == "admin")).scalar_one()
        assert len(admin_role.users) == 1


def test_second_bootstrap_rolls_back_without_changing_authority(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """Refuse every later bootstrap without users or role joins changing."""
    with auth_session_factory() as session:
        bootstrap_first_admin(
            session,
            email="admin@example.com",
            display_name="Admin",
            password="first admin phrase!",
        )

    with auth_session_factory() as session:
        with pytest.raises(BootstrapAdminError, match="users already exist"):
            bootstrap_first_admin(
                session,
                email="second@example.com",
                display_name="Second",
                password="second admin phrase!",
            )

    with auth_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
        assert session.scalar(select(func.count()).select_from(Role)) == 4
