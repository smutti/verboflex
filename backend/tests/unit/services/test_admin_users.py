"""Transactional service contracts for administrator-managed user authority."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.passwords import hash_password, verify_password
from verboflex.models.auth_session import AuthSession
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.schemas.users import RoleName
from verboflex.services import admin_users

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
FIXED_ROLE_ORDER = tuple(RoleName)
ALL_ROLE_COMBINATIONS = tuple(
    frozenset(selection)
    for size in range(1, len(FIXED_ROLE_ORDER) + 1)
    for selection in combinations(FIXED_ROLE_ORDER, size)
)


@pytest.fixture(scope="module")
def service_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate an isolated PostgreSQL database for service invariants."""
    database_name = f"verboflex_admin_user_service_{uuid4().hex}"
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
def clean_service_database(service_session_factory: sessionmaker[Session]) -> Iterator[None]:
    """Keep service cases independent while preserving migrated fixed roles."""
    with service_session_factory.begin() as session:
        session.query(AuthSession).delete()
        session.query(User).delete()
    yield


def _required_service(name: str) -> Callable[..., Any]:
    """Fail RED at behavior execution rather than during test collection."""
    implementation = getattr(admin_users, name, None)
    assert callable(implementation), f"admin user service is missing {name}"
    return cast(Callable[..., Any], implementation)


def _seed_user(
    factory: sessionmaker[Session],
    *,
    email: str,
    roles: tuple[RoleName, ...],
    active: bool = True,
    token_version: int = 0,
) -> UUID:
    user_id = uuid4()
    with factory.begin() as session:
        durable_roles = list(
            session.execute(
                select(Role).where(Role.name.in_(role.value for role in roles))
            ).scalars()
        )
        session.add(
            User(
                id=user_id,
                email=email,
                display_name=email.split("@", 1)[0].title(),
                hashed_password=hash_password(f"initial password for {email}!"),
                is_active=active,
                must_change_password=False,
                token_version=token_version,
                roles=durable_roles,
            )
        )
    return user_id


def _add_live_session(factory: sessionmaker[Session], user_id: UUID, token_hash: str) -> UUID:
    auth_session_id = uuid4()
    with factory.begin() as session:
        session.add(
            AuthSession(
                id=auth_session_id,
                user_id=user_id,
                family_id=uuid4(),
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
    return auth_session_id


@pytest.mark.parametrize("requested_roles", ALL_ROLE_COMBINATIONS)
def test_every_non_empty_role_combination_round_trips_on_the_same_user_uuid(
    service_session_factory: sessionmaker[Session],
    requested_roles: frozenset[RoleName],
) -> None:
    """All fifteen additive role sets share one identity and stable role order."""
    update_user = _required_service("update_admin_user")
    actor_id = _seed_user(
        service_session_factory,
        email="admin@example.com",
        roles=(RoleName.ADMIN,),
    )
    target_id = _seed_user(
        service_session_factory,
        email="target@example.com",
        roles=(RoleName.VIEWER,),
    )

    with service_session_factory() as session:
        updated = update_user(
            session,
            actor_id=actor_id,
            target_id=target_id,
            display_name="Target User",
            roles=requested_roles,
        )

    assert updated.id == target_id
    assert updated.roles == tuple(role for role in FIXED_ROLE_ORDER if role in requested_roles)
    with service_session_factory() as session:
        target = session.get_one(User, target_id)
        assert target.id == target_id
        assert [RoleName(role.name) for role in target.roles] == list(updated.roles)


def test_user_roles_relationship_declares_fixed_role_order() -> None:
    """The ORM loader must not rely on PostgreSQL's unspecified row order."""
    relationship_order = User.roles.property.order_by

    assert relationship_order is not False
    assert tuple(str(clause) for clause in relationship_order) == ("roles.name",)


def test_identical_normalized_update_is_a_non_mutating_noop(
    service_session_factory: sessionmaker[Session],
) -> None:
    """Normalized display and role equality preserve authority and session state."""
    update_user = _required_service("update_admin_user")
    actor_id = _seed_user(
        service_session_factory,
        email="admin@example.com",
        roles=(RoleName.ADMIN,),
    )
    target_id = _seed_user(
        service_session_factory,
        email="target@example.com",
        roles=(RoleName.TRANSLATOR, RoleName.VIEWER),
        token_version=7,
    )
    auth_session_id = _add_live_session(service_session_factory, target_id, "a" * 64)
    with service_session_factory() as session:
        before = session.get_one(User, target_id)
        previous_hash = before.hashed_password
        previous_updated_at = before.updated_at

    with service_session_factory() as session:
        result = update_user(
            session,
            actor_id=actor_id,
            target_id=target_id,
            display_name="  Target  ",
            roles=frozenset((RoleName.VIEWER, RoleName.TRANSLATOR)),
        )

    assert result.id == target_id
    with service_session_factory() as session:
        target = session.get_one(User, target_id)
        auth_session = session.get_one(AuthSession, auth_session_id)
        assert target.display_name == "Target"
        assert target.token_version == 7
        assert target.hashed_password == previous_hash
        assert target.updated_at == previous_updated_at
        assert auth_session.revoked_at is None


def test_empty_roles_and_self_admin_removal_fail_without_mutation(
    service_session_factory: sessionmaker[Session],
) -> None:
    """Role validation rejects empty authority and self-admin removal atomically."""
    update_user = _required_service("update_admin_user")
    actor_id = _seed_user(
        service_session_factory,
        email="admin@example.com",
        roles=(RoleName.ADMIN, RoleName.VIEWER),
        token_version=3,
    )
    with service_session_factory() as session:
        actor = session.get_one(User, actor_id)
        before = (actor.display_name, tuple(role.name for role in actor.roles), actor.token_version)

    for roles in (frozenset(), frozenset((RoleName.VIEWER,))):
        with (
            service_session_factory() as session,
            pytest.raises((admin_users.AdminUserInputError, admin_users.AdminUserConflict)),
        ):
            update_user(
                session,
                actor_id=actor_id,
                target_id=actor_id,
                display_name="Changed",
                roles=roles,
            )

    with service_session_factory() as session:
        actor = session.get_one(User, actor_id)
        assert (
            actor.display_name,
            tuple(role.name for role in actor.roles),
            actor.token_version,
        ) == before


def test_reset_and_reactivation_always_issue_fresh_credentials_and_revoke_authority(
    service_session_factory: sessionmaker[Session],
) -> None:
    """Repeated authority replacement never resurrects an older credential or session."""
    reset_password = _required_service("reset_admin_user_password")
    deactivate = _required_service("deactivate_admin_user")
    reactivate = _required_service("reactivate_admin_user")
    actor_id = _seed_user(
        service_session_factory,
        email="admin@example.com",
        roles=(RoleName.ADMIN,),
    )
    target_id = _seed_user(
        service_session_factory,
        email="target@example.com",
        roles=(RoleName.VIEWER,),
        token_version=4,
    )
    first_session_id = _add_live_session(service_session_factory, target_id, "b" * 64)

    with service_session_factory() as session:
        first_reset = reset_password(session, actor_id=actor_id, target_id=target_id)
    second_session_id = _add_live_session(service_session_factory, target_id, "c" * 64)
    with service_session_factory() as session:
        second_reset = reset_password(session, actor_id=actor_id, target_id=target_id)
    assert first_reset.temporary_password != second_reset.temporary_password

    with service_session_factory() as session:
        target = session.get_one(User, target_id)
        assert verify_password(second_reset.temporary_password, target.hashed_password) is True
        assert verify_password(first_reset.temporary_password, target.hashed_password) is False
        assert target.must_change_password is True
        assert target.token_version == 6
        assert session.get_one(AuthSession, first_session_id).revoked_at is not None
        assert session.get_one(AuthSession, second_session_id).revoked_at is not None

    with service_session_factory() as session:
        deactivated = deactivate(session, actor_id=actor_id, target_id=target_id)
    assert deactivated.is_active is False
    third_session_id = _add_live_session(service_session_factory, target_id, "d" * 64)
    with service_session_factory() as session:
        first_reactivation = reactivate(session, actor_id=actor_id, target_id=target_id)
    with service_session_factory() as session:
        deactivate(session, actor_id=actor_id, target_id=target_id)
    with service_session_factory() as session:
        second_reactivation = reactivate(session, actor_id=actor_id, target_id=target_id)

    assert first_reactivation.temporary_password != second_reactivation.temporary_password
    with service_session_factory() as session:
        target = session.get_one(User, target_id)
        assert target.is_active is True
        assert target.must_change_password is True
        assert (
            verify_password(second_reactivation.temporary_password, target.hashed_password) is True
        )
        assert (
            verify_password(first_reactivation.temporary_password, target.hashed_password) is False
        )
        assert verify_password(second_reset.temporary_password, target.hashed_password) is False
        assert target.token_version == 10
        assert session.get_one(AuthSession, third_session_id).revoked_at is not None


def test_cli_password_and_deactivation_wrappers_reuse_the_shared_service(
    service_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI delegates authority mutations instead of retaining a second transaction."""
    from verboflex import cli

    calls: list[tuple[str, str]] = []

    def fake_replace(_session: Session, *, email: str, password: str) -> None:
        calls.append((email, password))

    def fake_deactivate(_session: Session, *, email: str, now: datetime | None = None) -> None:
        del now
        calls.append((email, "deactivate"))

    monkeypatch.setattr(admin_users, "replace_user_password", fake_replace, raising=False)
    monkeypatch.setattr(admin_users, "deactivate_user_by_email", fake_deactivate, raising=False)

    with service_session_factory() as session:
        cli.reset_user_password(
            session,
            email=" ADMIN@EXAMPLE.COM ",
            password="replacement phrase!",
        )
    with service_session_factory() as session:
        cli.deactivate_user(session, email=" TARGET@EXAMPLE.COM ")

    assert calls == [
        (" ADMIN@EXAMPLE.COM ", "replacement phrase!"),
        (" TARGET@EXAMPLE.COM ", "deactivate"),
    ]
