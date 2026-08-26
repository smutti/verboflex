"""Real PostgreSQL races for global administrator and credential authority."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.passwords import hash_password, verify_password
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.schemas.users import RoleName
from verboflex.services import admin_users

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)


@pytest.fixture(scope="module")
def concurrency_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate an isolated database used by independent concurrent sessions."""
    database_name = f"verboflex_admin_user_race_{uuid4().hex}"
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
def clean_concurrency_database(
    concurrency_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    """Delete mutable authority rows between races."""
    with concurrency_session_factory.begin() as session:
        session.query(User).delete()
    yield


def _required_service(name: str) -> Callable[..., Any]:
    implementation = getattr(admin_users, name, None)
    assert callable(implementation), f"admin user service is missing {name}"
    return cast(Callable[..., Any], implementation)


def _seed_user(
    factory: sessionmaker[Session],
    *,
    email: str,
    roles: tuple[RoleName, ...],
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
                must_change_password=False,
                token_version=token_version,
                roles=durable_roles,
            )
        )
    return user_id


def test_concurrent_cross_deactivation_cannot_remove_the_last_active_admin(
    concurrency_session_factory: sessionmaker[Session],
) -> None:
    """Two admins deactivating each other produce one winner and one safe conflict."""
    deactivate = _required_service("deactivate_admin_user")
    first_id = _seed_user(
        concurrency_session_factory,
        email="first@example.com",
        roles=(RoleName.ADMIN,),
    )
    second_id = _seed_user(
        concurrency_session_factory,
        email="second@example.com",
        roles=(RoleName.ADMIN,),
    )

    def attempt(pair: tuple[UUID, UUID]) -> str:
        actor_id, target_id = pair
        try:
            with concurrency_session_factory() as session:
                deactivate(session, actor_id=actor_id, target_id=target_id)
        except (admin_users.AdminUserAuthorityError, admin_users.AdminUserConflict):
            return "refused"
        return "deactivated"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, ((first_id, second_id), (second_id, first_id))))

    assert sorted(outcomes) == ["deactivated", "refused"]
    with concurrency_session_factory() as session:
        active_admins = session.scalar(
            select(func.count())
            .select_from(User)
            .join(User.roles)
            .where(User.is_active.is_(True), Role.name == RoleName.ADMIN.value)
        )
        assert active_admins == 1


def test_concurrent_cross_role_removal_cannot_remove_the_last_active_admin(
    concurrency_session_factory: sessionmaker[Session],
) -> None:
    """Role races share the same global lock and preserve one active admin."""
    update_user = _required_service("update_admin_user")
    first_id = _seed_user(
        concurrency_session_factory,
        email="first@example.com",
        roles=(RoleName.ADMIN, RoleName.VIEWER),
    )
    second_id = _seed_user(
        concurrency_session_factory,
        email="second@example.com",
        roles=(RoleName.ADMIN, RoleName.VIEWER),
    )

    def attempt(pair: tuple[UUID, UUID]) -> str:
        actor_id, target_id = pair
        try:
            with concurrency_session_factory() as session:
                update_user(
                    session,
                    actor_id=actor_id,
                    target_id=target_id,
                    display_name="Role target",
                    roles=frozenset((RoleName.VIEWER,)),
                )
        except (admin_users.AdminUserAuthorityError, admin_users.AdminUserConflict):
            return "refused"
        return "updated"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, ((first_id, second_id), (second_id, first_id))))

    assert sorted(outcomes) == ["refused", "updated"]
    with concurrency_session_factory() as session:
        active_admins = session.scalar(
            select(func.count())
            .select_from(User)
            .join(User.roles)
            .where(User.is_active.is_(True), Role.name == RoleName.ADMIN.value)
        )
        assert active_admins == 1


def test_concurrent_resets_serialize_and_only_the_last_committed_secret_is_valid(
    concurrency_session_factory: sessionmaker[Session],
) -> None:
    """Same-target password authority advances once per committed reset."""
    reset_password = _required_service("reset_admin_user_password")
    actor_id = _seed_user(
        concurrency_session_factory,
        email="admin@example.com",
        roles=(RoleName.ADMIN,),
    )
    target_id = _seed_user(
        concurrency_session_factory,
        email="target@example.com",
        roles=(RoleName.VIEWER,),
        token_version=9,
    )

    def attempt(_index: int) -> str:
        with concurrency_session_factory() as session:
            result = reset_password(session, actor_id=actor_id, target_id=target_id)
        return cast(str, result.temporary_password)

    with ThreadPoolExecutor(max_workers=2) as executor:
        secrets = list(executor.map(attempt, range(2)))

    assert secrets[0] != secrets[1]
    with concurrency_session_factory() as session:
        target = session.get_one(User, target_id)
        assert target.token_version == 11
        assert sum(verify_password(secret, target.hashed_password) for secret in secrets) == 1
