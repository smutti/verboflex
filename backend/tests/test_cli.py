"""Privileged CLI contracts for survivor-safe administrator deactivation."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex import cli
from verboflex.auth.passwords import hash_password
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.schemas.users import RoleName
from verboflex.services import admin_users

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)


@pytest.fixture(scope="module")
def cli_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for CLI authority tests."""
    database_name = f"verboflex_admin_user_cli_{uuid4().hex}"
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
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


@pytest.fixture(autouse=True)
def clean_cli_database(cli_session_factory: sessionmaker[Session]) -> Iterator[None]:
    """Keep CLI cases independent while preserving the migrated role vocabulary."""
    with cli_session_factory.begin() as session:
        session.query(User).delete()
    yield


def _seed_admin(factory: sessionmaker[Session], *, email: str) -> UUID:
    user_id = uuid4()
    with factory.begin() as session:
        admin_role = session.execute(
            select(Role).where(Role.name == RoleName.ADMIN.value)
        ).scalar_one()
        session.add(
            User(
                id=user_id,
                email=email,
                display_name=email.split("@", 1)[0].title(),
                hashed_password=hash_password(f"initial password for {email}!"),
                must_change_password=False,
                roles=[admin_role],
            )
        )
    return user_id


def _session_provider(
    factory: sessionmaker[Session],
) -> Callable[[], AbstractContextManager[Session]]:
    return factory


def _active_admin_count(factory: sessionmaker[Session]) -> int:
    with factory() as session:
        count = session.scalar(
            select(func.count())
            .select_from(User)
            .join(User.roles)
            .where(User.is_active.is_(True), Role.name == RoleName.ADMIN.value)
        )
    return int(count or 0)


def test_cli_sole_admin_deactivation_fails_without_changing_authority(
    cli_session_factory: sessionmaker[Session],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The process adapter maps the shared survivor conflict to a bounded failure."""
    admin_id = _seed_admin(cli_session_factory, email="admin@example.com")

    exit_code = cli.main(
        ["deactivate-user", "--email", " ADMIN@EXAMPLE.COM "],
        session_provider=_session_provider(cli_session_factory),
    )

    output = capsys.readouterr()
    assert exit_code == 1
    assert output.out == ""
    assert output.err == "user lifecycle conflict\n"
    assert "admin@example.com" not in output.err
    with cli_session_factory() as session:
        admin = session.get_one(User, admin_id)
        assert admin.is_active is True
        assert admin.token_version == 0
    assert _active_admin_count(cli_session_factory) == 1


def test_cli_two_admin_deactivation_succeeds_once_then_remains_bounded(
    cli_session_factory: sessionmaker[Session],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One valid transition leaves one survivor; missing and inactive targets stay bounded."""
    _seed_admin(cli_session_factory, email="first@example.com")
    _seed_admin(cli_session_factory, email="second@example.com")

    first_exit = cli.main(
        ["deactivate-user", "--email", " FIRST@EXAMPLE.COM "],
        session_provider=_session_provider(cli_session_factory),
    )
    first_output = capsys.readouterr()
    repeated_exit = cli.main(
        ["deactivate-user", "--email", "first@example.com"],
        session_provider=_session_provider(cli_session_factory),
    )
    repeated_output = capsys.readouterr()
    missing_exit = cli.main(
        ["deactivate-user", "--email", "missing@example.com"],
        session_provider=_session_provider(cli_session_factory),
    )
    missing_output = capsys.readouterr()

    assert first_exit == 0
    assert first_output.out == "Account deactivated; all sessions revoked.\n"
    assert first_output.err == ""
    assert repeated_exit == 1
    assert repeated_output.out == ""
    assert repeated_output.err == "deactivation refused: account unavailable\n"
    assert missing_exit == 1
    assert missing_output.out == ""
    assert missing_output.err == "deactivation refused: account unavailable\n"
    assert _active_admin_count(cli_session_factory) == 1


def test_cli_adapter_invokes_the_shared_service_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI wrapper contains no user-row transaction or lifecycle mutation."""
    calls: list[tuple[Session, str]] = []

    def fake_deactivate(
        session: Session,
        *,
        email: str,
        now: datetime | None = None,
    ) -> None:
        del now
        calls.append((session, email))

    session = cast(Session, object())
    monkeypatch.setattr(admin_users, "deactivate_user_by_email", fake_deactivate)

    cli.deactivate_user(session, email=" target@example.com ")

    assert calls == [(session, " target@example.com ")]
