"""Real-PostgreSQL contract for the complete reversible application schema."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
EXPECTED_TABLES = {
    "auth_sessions",
    "bitbucket_connections",
    "preview_jobs",
    "product_mapping_allowed_targets",
    "product_mapping_repository_sides",
    "product_repository_mappings",
    "product_revisions",
    "products",
    "repositories",
    "roles",
    "user_roles",
    "users",
}
EXPECTED_ROLES = {
    "admin",
    "product_manager_reviewer",
    "translator",
    "viewer",
}


@pytest.fixture
def migrated_database() -> Iterator[tuple[Config, Engine]]:
    """Create an isolated PostgreSQL database and remove it after rehearsal."""
    database_name = f"verboflex_0105_{uuid4().hex}"
    with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
        create_database = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        admin_connection.execute(create_database)

    database_url = ADMIN_DATABASE_URL.rsplit("/", 1)[0] + f"/{database_name}"
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option(
        "sqlalchemy.url", database_url.replace("postgresql://", "postgresql+psycopg://")
    )
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://"))

    try:
        yield config, engine
    finally:
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def test_complete_schema_upgrades_downgrades_and_upgrades_reversibly(
    migrated_database: tuple[Config, Engine],
) -> None:
    """Create the exact Phase 2 schema twice without leaving residual objects."""
    config, engine = migrated_database

    command.upgrade(config, "head")
    assert_complete_schema(engine)

    command.downgrade(config, "base")
    assert EXPECTED_TABLES.isdisjoint(inspect(engine).get_table_names())

    command.upgrade(config, "head")
    assert_complete_schema(engine)


def assert_complete_schema(engine: Engine) -> None:
    """Assert the complete authority/configuration tables and the original auth seed."""
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) >= EXPECTED_TABLES

    user_columns = {column["name"]: column for column in inspector.get_columns("users")}
    assert set(user_columns) == {
        "id",
        "email",
        "display_name",
        "hashed_password",
        "is_active",
        "must_change_password",
        "token_version",
        "created_at",
        "updated_at",
    }
    assert all(user_columns[name]["nullable"] is False for name in user_columns)

    session_columns = {column["name"]: column for column in inspector.get_columns("auth_sessions")}
    assert set(session_columns) == {
        "id",
        "user_id",
        "family_id",
        "parent_id",
        "token_hash",
        "used_at",
        "revoked_at",
        "expires_at",
        "created_at",
    }
    assert session_columns["parent_id"]["nullable"] is True
    assert session_columns["used_at"]["nullable"] is True
    assert session_columns["revoked_at"]["nullable"] is True

    user_role_pk = inspector.get_pk_constraint("user_roles")
    assert set(user_role_pk["constrained_columns"]) == {"user_id", "role_id"}

    foreign_keys = {
        (foreign_key["constrained_columns"][0], foreign_key["referred_table"]): (
            foreign_key.get("options") or {}
        ).get("ondelete")
        for table_name in ("user_roles", "auth_sessions")
        for foreign_key in inspector.get_foreign_keys(table_name)
    }
    assert foreign_keys[("user_id", "users")] == "CASCADE"
    assert foreign_keys[("role_id", "roles")] == "RESTRICT"
    assert foreign_keys[("parent_id", "auth_sessions")] == "RESTRICT"

    index_names = {
        index["name"]
        for table_name in EXPECTED_TABLES
        for index in inspector.get_indexes(table_name)
    }
    assert {
        "uq_users_email",
        "uq_roles_name",
        "ix_auth_sessions_user_id",
        "ix_auth_sessions_family_id",
        "uq_auth_sessions_token_hash",
        "uq_auth_sessions_parent_id",
    } <= index_names

    expected_phase2_indexes = {
        "ix_preview_jobs_candidate_revision_id",
        "ix_preview_jobs_mapping_digest_attempt",
        "ix_preview_jobs_product_id",
        "ix_product_repository_mappings_revision_id",
        "ix_product_revisions_product_id",
        "uq_product_mapping_allowed_targets_one_default",
    }
    assert expected_phase2_indexes <= index_names

    expected_unique_constraints = {
        "products": {"uq_products_name_key"},
        "repositories": {"uq_repositories_provider_identity"},
        "product_repository_mappings": {
            "uq_product_repository_mappings_confirmed_preview_job",
            "uq_product_repository_mappings_revision_identity",
        },
        "preview_jobs": {"uq_preview_jobs_digest_attempt"},
    }
    for table_name, constraint_names in expected_unique_constraints.items():
        actual_names = {
            constraint["name"] for constraint in inspector.get_unique_constraints(table_name)
        }
        assert constraint_names <= actual_names

    with engine.connect() as connection:
        roles = connection.execute(text("SELECT name FROM roles ORDER BY name")).scalars().all()
        assert roles == sorted(EXPECTED_ROLES)
        normalized_check = connection.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_users_email_normalized'"
            )
        ).scalar_one()
        assert "lower" in normalized_check


def test_migration_constraints_reject_duplicates_and_roll_back_atomically(
    migrated_database: tuple[Config, Engine],
) -> None:
    """Database constraints reject malformed authority without partial writes."""
    config, engine = migrated_database
    command.upgrade(config, "head")

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users "
                "(email, display_name, hashed_password) "
                "VALUES ('Mixed@Example.COM', 'Bad', 'not-a-real-secret')"
            )
        )

    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM roles")).scalar_one() == 4


def test_declarative_metadata_contains_every_auth_model() -> None:
    """Alembic imports the complete model graph before assigning metadata."""
    from verboflex import models  # noqa: F401
    from verboflex.db.base import Base

    assert set(Base.metadata.tables) >= EXPECTED_TABLES
