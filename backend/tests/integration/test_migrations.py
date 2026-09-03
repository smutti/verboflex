"""Real-PostgreSQL contract for the complete reversible application schema."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import connect, sql
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
EXPECTED_TABLES = {
    "active_revision_revalidation_confirmations",
    "auth_sessions",
    "bitbucket_connections",
    "import_executions",
    "import_jobs",
    "import_rewrite_deltas",
    "import_rewrite_proposals",
    "import_source_references",
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
PREVIEW_WATCHDOG_INDEX = "ix_preview_jobs_watchdog_state_started_at"


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
        PREVIEW_WATCHDOG_INDEX,
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


def _seed_import_schema_graph(engine: Engine) -> dict[str, UUID]:
    """Create two independent published mapping owners for forged-identity checks."""
    identities = {
        "product": uuid4(),
        "revision": uuid4(),
        "mapping": uuid4(),
        "repository": uuid4(),
        "foreign_product": uuid4(),
        "foreign_revision": uuid4(),
        "foreign_mapping": uuid4(),
        "foreign_repository": uuid4(),
    }
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO products (id, display_name, name_key, is_active) VALUES "
                "(:product, 'Import owner', :product_key, true), "
                "(:foreign_product, 'Foreign owner', :foreign_product_key, true)"
            ),
            {
                **identities,
                "product_key": f"import-owner-{identities['product']}",
                "foreign_product_key": f"foreign-owner-{identities['foreign_product']}",
            },
        )
        connection.execute(
            text(
                "INSERT INTO product_revisions "
                "(id, product_id, display_name, name_key, description, version, "
                "is_published, published_at) VALUES "
                "(:revision, :product, 'Import owner', :product_key, 'published', 1, "
                "false, NULL), "
                "(:foreign_revision, :foreign_product, 'Foreign owner', "
                ":foreign_product_key, 'published', 1, false, NULL)"
            ),
            {
                **identities,
                "product_key": f"import-owner-{identities['product']}",
                "foreign_product_key": f"foreign-owner-{identities['foreign_product']}",
            },
        )
        connection.execute(
            text(
                "INSERT INTO repositories "
                "(id, workspace, repository_slug, descriptive_name, descriptive_name_key) "
                "VALUES (:repository, 'import-workspace', :repository_slug, "
                "'Import repository', 'import repository'), "
                "(:foreign_repository, 'foreign-workspace', :foreign_repository_slug, "
                "'Foreign repository', 'foreign repository')"
            ),
            {
                **identities,
                "repository_slug": f"import-{identities['repository'].hex[:12]}",
                "foreign_repository_slug": (f"foreign-{identities['foreign_repository'].hex[:12]}"),
            },
        )
        connection.execute(
            text(
                "INSERT INTO product_repository_mappings "
                "(id, revision_id, topology, identity_key) VALUES "
                "(:mapping, :revision, 'direct', :mapping_key), "
                "(:foreign_mapping, :foreign_revision, 'direct', :foreign_mapping_key)"
            ),
            {
                **identities,
                "mapping_key": f"import-{identities['mapping']}",
                "foreign_mapping_key": f"foreign-{identities['foreign_mapping']}",
            },
        )
        connection.execute(
            text(
                "INSERT INTO product_mapping_repository_sides "
                "(mapping_id, role, repository_id, source_branch) VALUES "
                "(:mapping, 'direct', :repository, 'main'), "
                "(:foreign_mapping, 'direct', :foreign_repository, 'foreign-main')"
            ),
            identities,
        )
        connection.execute(
            text(
                "UPDATE product_revisions SET is_published = true, "
                "published_at = CURRENT_TIMESTAMP WHERE id IN (:revision, :foreign_revision)"
            ),
            identities,
        )
        connection.execute(
            text(
                "UPDATE products SET active_revision_id = CASE "
                "WHEN id = :product THEN :revision ELSE :foreign_revision END "
                "WHERE id IN (:product, :foreign_product)"
            ),
            identities,
        )
    return identities


def _insert_import_execution(
    engine: Engine,
    identities: dict[str, UUID],
    *,
    state: str = "running",
) -> tuple[UUID, UUID]:
    import_id = uuid4()
    execution_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_jobs "
                "(id, product_id, revision_id, mapping_id, topology, state, "
                "current_execution_id, retry_count, latest_execution_at) VALUES "
                "(:import_id, :product, :revision, :mapping, 'direct', 'running', "
                ":execution_id, 0, CURRENT_TIMESTAMP)"
            ),
            {**identities, "import_id": import_id, "execution_id": execution_id},
        )
        connection.execute(
            text(
                "INSERT INTO import_executions "
                "(id, import_job_id, sequence, state, connection_generation, started_at, "
                "finished_at) VALUES (:execution_id, :import_id, 1, :state, 1, "
                "CURRENT_TIMESTAMP, CASE WHEN CAST(:state AS varchar) "
                "IN ('succeeded', 'failed') "
                "THEN CURRENT_TIMESTAMP ELSE NULL END)"
            ),
            {
                "execution_id": execution_id,
                "import_id": import_id,
                "state": state,
            },
        )
    return import_id, execution_id


def test_import_schema_is_reversible_and_database_authoritative(
    migrated_database: tuple[Config, Engine],
) -> None:
    """Phase 3 objects enforce named state, ownership, identity, and index rules."""
    config, engine = migrated_database
    command.upgrade(config, "0011_active_revision_revalidations")
    assert {
        "import_jobs",
        "import_executions",
        "import_source_references",
    }.isdisjoint(inspect(engine).get_table_names())

    command.upgrade(config, "0012_import_jobs")
    inspector = inspect(engine)
    assert {
        "pk_import_jobs",
        "uq_import_jobs_mapping",
        "fk_import_jobs_owned_revision",
        "fk_import_jobs_owned_mapping",
        "fk_import_jobs_current_execution",
        "fk_import_jobs_active_baseline",
        "ck_import_jobs_state_error_payload",
    } <= _constraint_names(engine, "import_jobs")
    assert {
        "pk_import_executions",
        "uq_import_executions_id_job",
        "uq_import_executions_job_sequence",
        "ck_import_executions_positive_sequence",
        "ck_import_executions_state_timestamps",
    } <= _constraint_names(engine, "import_executions")
    assert {
        "pk_import_source_references",
        "uq_import_source_references_side_path",
        "ck_import_source_references_commit_hash_sha1",
        "ck_import_source_references_position_non_negative",
    } <= _constraint_names(engine, "import_source_references")
    assert {
        "ix_import_jobs_revision_mapping",
        "ix_import_executions_job_sequence",
        "ix_import_source_references_execution_side_position",
    } <= {
        index["name"]
        for table_name in (
            "import_jobs",
            "import_executions",
            "import_source_references",
        )
        for index in inspector.get_indexes(table_name)
    }

    identities = _seed_import_schema_graph(engine)
    import_id, execution_id = _insert_import_execution(engine, identities)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_source_references "
                "(execution_id, position, repository_side, repository_id, source_branch, "
                "commit_hash, path, size_bytes, sha256) VALUES "
                "(:execution_id, 0, 'direct', :repository, 'main', :commit_hash, "
                "'values/strings.xml', 10, :sha256)"
            ),
            {
                **identities,
                "execution_id": execution_id,
                "commit_hash": "a" * 40,
                "sha256": "b" * 64,
            },
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_jobs "
                "(id, product_id, revision_id, mapping_id, topology, state, "
                "current_execution_id, latest_execution_at) VALUES "
                "(:id, :foreign_product, :revision, :mapping, 'direct', 'queued', "
                ":execution_id, CURRENT_TIMESTAMP)"
            ),
            {**identities, "id": uuid4(), "execution_id": uuid4()},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_jobs "
                "(id, product_id, revision_id, mapping_id, topology, state, "
                "current_execution_id, latest_execution_at) VALUES "
                "(:id, :product, :revision, :mapping, 'direct', 'queued', "
                ":execution_id, CURRENT_TIMESTAMP)"
            ),
            {**identities, "id": uuid4(), "execution_id": uuid4()},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE import_jobs SET state = 'current', "
                "active_baseline_execution_id = NULL WHERE id = :id"
            ),
            {"id": import_id},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_executions "
                "(id, import_job_id, sequence, state, connection_generation) VALUES "
                "(:id, :import_id, 0, 'queued', 1)"
            ),
            {"id": uuid4(), "import_id": import_id},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_source_references "
                "(execution_id, position, repository_side, repository_id, source_branch, "
                "commit_hash, path, size_bytes, sha256) VALUES "
                "(:execution_id, 1, 'direct', :repository, 'main', 'not-a-commit', "
                "'values/other.xml', 1, :sha256)"
            ),
            {**identities, "execution_id": execution_id, "sha256": "c" * 64},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_source_references "
                "(execution_id, position, repository_side, repository_id, source_branch, "
                "commit_hash, path, size_bytes, sha256) VALUES "
                "(:execution_id, -1, 'direct', :repository, 'main', :commit_hash, "
                "'values/negative.xml', 1, :sha256)"
            ),
            {
                **identities,
                "execution_id": execution_id,
                "commit_hash": "c" * 40,
                "sha256": "d" * 64,
            },
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_source_references "
                "(execution_id, position, repository_side, repository_id, source_branch, "
                "commit_hash, path, size_bytes, sha256) VALUES "
                "(:execution_id, 1, 'direct', :repository, 'main', :commit_hash, "
                "'values/strings.xml', 10, :sha256)"
            ),
            {
                **identities,
                "execution_id": execution_id,
                "commit_hash": "a" * 40,
                "sha256": "b" * 64,
            },
        )
    with (
        pytest.raises(DBAPIError, match="source reference ownership"),
        engine.begin() as connection,
    ):
        connection.execute(
            text(
                "INSERT INTO import_source_references "
                "(execution_id, position, repository_side, repository_id, source_branch, "
                "commit_hash, path, size_bytes, sha256) VALUES "
                "(:execution_id, 1, 'direct', :foreign_repository, 'foreign-main', "
                ":commit_hash, 'values/foreign.xml', 1, :sha256)"
            ),
            {
                **identities,
                "execution_id": execution_id,
                "commit_hash": "d" * 40,
                "sha256": "e" * 64,
            },
        )

    command.downgrade(config, "0011_active_revision_revalidations")
    assert {
        "import_jobs",
        "import_executions",
        "import_source_references",
    }.isdisjoint(inspect(engine).get_table_names())
    command.upgrade(config, "head")
    assert {
        "import_jobs",
        "import_executions",
        "import_source_references",
    } <= set(inspect(engine).get_table_names())


def test_rewrite_migration_is_reversible_complete_and_ownership_safe(
    migrated_database: tuple[Config, Engine],
) -> None:
    config, engine = migrated_database
    command.upgrade(config, "0012_import_jobs")
    identities = _seed_import_schema_graph(engine)
    import_id, baseline_execution_id = _insert_import_execution(
        engine,
        identities,
        state="succeeded",
    )
    proposed_execution_id = uuid4()
    proposal_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE import_jobs SET state = 'current', "
                "active_baseline_execution_id = :baseline WHERE id = :import_id"
            ),
            {"baseline": baseline_execution_id, "import_id": import_id},
        )
        connection.execute(
            text(
                "INSERT INTO import_executions "
                "(id, import_job_id, sequence, state, connection_generation, "
                "started_at, finished_at) VALUES "
                "(:id, :import_id, 2, 'succeeded', 1, CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            ),
            {"id": proposed_execution_id, "import_id": import_id},
        )
        connection.execute(
            text(
                "UPDATE import_jobs SET current_execution_id = :execution_id "
                "WHERE id = :import_id"
            ),
            {"execution_id": proposed_execution_id, "import_id": import_id},
        )

    command.upgrade(config, "0013_import_rewrite_proposals")
    inspector = inspect(engine)
    assert {"import_rewrite_proposals", "import_rewrite_deltas"} <= set(
        inspector.get_table_names()
    )
    assert {
        "pk_import_rewrite_proposals",
        "fk_import_rewrite_proposals_owned_mapping",
        "fk_import_rewrite_proposals_old_baseline",
        "fk_import_rewrite_proposals_proposed_execution",
        "ck_import_rewrite_proposals_complete_authority",
        "ck_import_rewrite_proposals_topology_commits",
    } <= _constraint_names(engine, "import_rewrite_proposals")
    assert {
        "pk_import_rewrite_deltas",
        "ck_import_rewrite_deltas_position_non_negative",
        "ck_import_rewrite_deltas_change_value",
    } <= _constraint_names(engine, "import_rewrite_deltas")

    insert_proposal = text(
        "INSERT INTO import_rewrite_proposals "
        "(id, import_job_id, product_id, revision_id, revision_version, mapping_id, "
        "topology, connection_generation, proposed_execution_id, "
        "old_baseline_execution_id, direct_repository_id, direct_old_commit_hash, "
        "direct_new_commit_hash, complete, digest, status) VALUES "
        "(:id, :import_id, :product, :revision, 7, :mapping, 'direct', 1, "
        ":proposed_execution_id, :baseline_execution_id, :repository, :old_commit, "
        ":new_commit, true, :digest, 'pending')"
    )
    with engine.begin() as connection:
        connection.execute(
            insert_proposal,
            {
                **identities,
                "id": proposal_id,
                "import_id": import_id,
                "proposed_execution_id": proposed_execution_id,
                "baseline_execution_id": baseline_execution_id,
                "old_commit": "1" * 40,
                "new_commit": "2" * 40,
                "digest": "a" * 64,
            },
        )
        connection.execute(
            text(
                "INSERT INTO import_rewrite_deltas "
                "(proposal_id, position, repository_side, change, path) VALUES "
                "(:proposal_id, 0, 'direct', 'modified', 'values/strings.xml')"
            ),
            {"proposal_id": proposal_id},
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_rewrite_proposals "
                "(id, import_job_id, product_id, revision_id, revision_version, mapping_id, "
                "topology, connection_generation, proposed_execution_id, "
                "old_baseline_execution_id, direct_repository_id, direct_old_commit_hash, "
                "direct_new_commit_hash, complete, digest, status) VALUES "
                "(:id, :import_id, :product, :revision, 7, :mapping, 'direct', 1, "
                ":proposed_execution_id, :baseline_execution_id, :repository, :old_commit, "
                ":new_commit, false, :digest, 'superseded')"
            ),
            {
                **identities,
                "id": uuid4(),
                "import_id": import_id,
                "proposed_execution_id": proposed_execution_id,
                "baseline_execution_id": baseline_execution_id,
                "old_commit": "1" * 40,
                "new_commit": "2" * 40,
                "digest": "b" * 64,
            },
        )

    command.downgrade(config, "0012_import_jobs")
    assert {"import_rewrite_proposals", "import_rewrite_deltas"}.isdisjoint(
        inspect(engine).get_table_names()
    )
    command.upgrade(config, "head")
    assert {"import_rewrite_proposals", "import_rewrite_deltas"} <= set(
        inspect(engine).get_table_names()
    )


def test_immutable_source_reference_and_terminal_execution_provenance(
    migrated_database: tuple[Config, Engine],
) -> None:
    """Terminal executions and their exact file references reject ORM-equivalent writes."""
    config, engine = migrated_database
    command.upgrade(config, "head")
    identities = _seed_import_schema_graph(engine)
    _import_id, execution_id = _insert_import_execution(
        engine,
        identities,
        state="succeeded",
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_source_references "
                "(execution_id, position, repository_side, repository_id, source_branch, "
                "commit_hash, path, size_bytes, sha256) VALUES "
                "(:execution_id, 0, 'direct', :repository, 'main', :commit_hash, "
                "'values/strings.xml', 10, :sha256)"
            ),
            {
                **identities,
                "execution_id": execution_id,
                "commit_hash": "a" * 40,
                "sha256": "b" * 64,
            },
        )

    with (
        pytest.raises(DBAPIError, match="terminal import execution is immutable"),
        engine.begin() as connection,
    ):
        connection.execute(
            text("UPDATE import_executions SET connection_generation = 2 WHERE id = :id"),
            {"id": execution_id},
        )
    with (
        pytest.raises(
            DBAPIError,
            match="terminal import source reference is immutable",
        ),
        engine.begin() as connection,
    ):
        connection.execute(
            text(
                "UPDATE import_source_references SET commit_hash = :commit_hash "
                "WHERE execution_id = :id"
            ),
            {"id": execution_id, "commit_hash": "f" * 40},
        )
    with (
        pytest.raises(
            DBAPIError,
            match="terminal import source reference is immutable",
        ),
        engine.begin() as connection,
    ):
        connection.execute(
            text("DELETE FROM import_source_references WHERE execution_id = :id"),
            {"id": execution_id},
        )


def test_client_credentials_credential_state_upgrade_downgrade_and_reupgrade(
    migrated_database: tuple[Config, Engine],
) -> None:
    """Permit access-only authority while every downgrade fails closed."""
    config, engine = migrated_database
    command.upgrade(config, "head")

    constraint_names = {
        constraint["name"]
        for constraint in inspect(engine).get_check_constraints("bitbucket_connections")
    }
    assert "ck_bitbucket_connections_credential_state" in constraint_names
    assert "ck_bitbucket_connections_credential_pair_state" not in constraint_names

    expires_at = datetime(2026, 8, 29, 16, 0, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE bitbucket_connections SET "
                "generation = 1, access_token_ciphertext = 'encrypted-access', "
                "refresh_token_ciphertext = NULL, scope_profile = 'repository', "
                "provider_expires_at = :expires_at, connected_at = :connected_at, "
                "revoked_at = NULL WHERE id = 1"
            ),
            {"expires_at": expires_at, "connected_at": expires_at},
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE bitbucket_connections SET "
                "access_token_ciphertext = NULL, refresh_token_ciphertext = 'refresh-only' "
                "WHERE id = 1"
            )
        )

    command.downgrade(config, "0007_preview_confirmations")
    with engine.connect() as connection:
        downgraded = connection.execute(
            text(
                "SELECT generation, access_token_ciphertext, refresh_token_ciphertext, "
                "scope_profile, provider_expires_at, connected_at, revoked_at "
                "FROM bitbucket_connections WHERE id = 1"
            )
        ).one()
    assert downgraded[0] == 2
    assert downgraded[1:6] == (None, None, None, None, None)
    assert downgraded[6] is not None
    assert {
        constraint["name"]
        for constraint in inspect(engine).get_check_constraints("bitbucket_connections")
    } >= {"ck_bitbucket_connections_credential_pair_state"}

    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE bitbucket_connections SET "
                "generation = 3, access_token_ciphertext = 'legacy-access', "
                "refresh_token_ciphertext = 'legacy-refresh', scope_profile = 'repository', "
                "provider_expires_at = :expires_at, connected_at = :connected_at, "
                "revoked_at = NULL WHERE id = 1"
            ),
            {"expires_at": expires_at, "connected_at": expires_at},
        )
    command.downgrade(config, "0007_preview_confirmations")
    with engine.connect() as connection:
        paired = connection.execute(
            text(
                "SELECT generation, access_token_ciphertext, refresh_token_ciphertext "
                "FROM bitbucket_connections WHERE id = 1"
            )
        ).one()
    assert paired == (3, "legacy-access", "legacy-refresh")

    command.upgrade(config, "head")
    with engine.connect() as connection:
        paired_after_reupgrade = connection.execute(
            text(
                "SELECT generation, access_token_ciphertext, refresh_token_ciphertext "
                "FROM bitbucket_connections WHERE id = 1"
            )
        ).one()
    assert paired_after_reupgrade == paired


def test_product_graph_integrity_upgrade_downgrade_and_reupgrade(
    migrated_database: tuple[Config, Engine],
) -> None:
    """Backfill revision identity and restore every graph guard reversibly."""
    config, engine = migrated_database
    command.upgrade(config, "0008_bitbucket_client_credentials")

    product_id = uuid4()
    active_revision_id = uuid4()
    candidate_revision_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO products "
                "(id, display_name, name_key, is_active) "
                "VALUES (:id, 'Migration Product', 'migration product', true)"
            ),
            {"id": product_id},
        )
        connection.execute(
            text(
                "INSERT INTO product_revisions "
                "(id, product_id, description, version, is_published, published_at) VALUES "
                "(:active_id, :product_id, 'active', 4, true, CURRENT_TIMESTAMP), "
                "(:candidate_id, :product_id, 'candidate', 5, false, NULL)"
            ),
            {
                "active_id": active_revision_id,
                "candidate_id": candidate_revision_id,
                "product_id": product_id,
            },
        )
        connection.execute(
            text(
                "UPDATE products SET active_revision_id = :active_id, "
                "candidate_revision_id = :candidate_id WHERE id = :product_id"
            ),
            {
                "active_id": active_revision_id,
                "candidate_id": candidate_revision_id,
                "product_id": product_id,
            },
        )

    command.upgrade(config, "head")
    revision_columns = {
        column["name"]: column for column in inspect(engine).get_columns("product_revisions")
    }
    assert revision_columns["display_name"]["nullable"] is False
    assert revision_columns["name_key"]["nullable"] is False
    with engine.connect() as connection:
        identities = connection.execute(
            text(
                "SELECT id, display_name, name_key FROM product_revisions "
                "WHERE product_id = :product_id ORDER BY id"
            ),
            {"product_id": product_id},
        ).all()
    assert identities == sorted(
        (
            (active_revision_id, "Migration Product", "migration product"),
            (candidate_revision_id, "Migration Product", "migration product"),
        )
    )

    assert {
        constraint["name"]
        for constraint in inspect(engine).get_unique_constraints("product_revisions")
    } >= {"uq_product_revisions_product_id_id"}
    assert {
        constraint["name"]
        for constraint in inspect(engine).get_unique_constraints("product_repository_mappings")
    } >= {"uq_product_mappings_revision_id_id"}
    assert {
        foreign_key["name"] for foreign_key in inspect(engine).get_foreign_keys("products")
    } >= {
        "fk_products_active_owned_revision",
        "fk_products_candidate_owned_revision",
    }
    assert {
        foreign_key["name"] for foreign_key in inspect(engine).get_foreign_keys("preview_jobs")
    } >= {
        "fk_preview_jobs_owned_revision",
        "fk_preview_jobs_owned_mapping",
    }

    with engine.connect() as connection:
        assert set(
            connection.execute(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname LIKE 'trg_guard_active_%'"
                )
            ).scalars()
        ) == {
            "trg_guard_active_product_revisions",
            "trg_guard_active_product_mappings",
            "trg_guard_active_mapping_sides",
            "trg_guard_active_mapping_targets",
        }

    command.downgrade(config, "0008_bitbucket_client_credentials")
    assert "display_name" not in {
        column["name"] for column in inspect(engine).get_columns("product_revisions")
    }
    assert {
        foreign_key["name"] for foreign_key in inspect(engine).get_foreign_keys("products")
    } >= {
        "fk_products_active_revision_id_product_revisions",
        "fk_products_candidate_revision_id_product_revisions",
    }
    assert {
        foreign_key["name"] for foreign_key in inspect(engine).get_foreign_keys("preview_jobs")
    } >= {
        "fk_preview_jobs_product_id_products",
        "fk_preview_jobs_candidate_revision_id_product_revisions",
        "fk_preview_jobs_mapping_id_product_repository_mappings",
    }
    with engine.connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM pg_proc "
                    "WHERE proname = 'verboflex_guard_active_revision_child'"
                )
            ).scalar_one()
            == 0
        )
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE NOT tgisinternal "
                    "AND tgname = 'trg_product_revisions_immutable_published'"
                )
            ).scalar_one()
            == 1
        )

    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT display_name FROM product_revisions WHERE id = :revision_id"),
                {"revision_id": candidate_revision_id},
            ).scalar_one()
            == "Migration Product"
        )


def test_product_graph_integrity_migration_rejects_legacy_cross_ownership(
    migrated_database: tuple[Config, Engine],
) -> None:
    """Legacy corruption fails with one bounded message and is never reparented."""
    config, engine = migrated_database
    command.upgrade(config, "0008_bitbucket_client_credentials")

    first_product_id = uuid4()
    second_product_id = uuid4()
    first_revision_id = uuid4()
    second_revision_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO products (id, display_name, name_key) VALUES "
                "(:first_id, 'First', 'first'), (:second_id, 'Second', 'second')"
            ),
            {"first_id": first_product_id, "second_id": second_product_id},
        )
        connection.execute(
            text(
                "INSERT INTO product_revisions "
                "(id, product_id, description, version, is_published) VALUES "
                "(:first_revision, :first_product, 'first', 1, false), "
                "(:second_revision, :second_product, 'second', 1, false)"
            ),
            {
                "first_revision": first_revision_id,
                "first_product": first_product_id,
                "second_revision": second_revision_id,
                "second_product": second_product_id,
            },
        )
        connection.execute(
            text(
                "UPDATE products SET candidate_revision_id = :foreign_revision "
                "WHERE id = :product_id"
            ),
            {"foreign_revision": second_revision_id, "product_id": first_product_id},
        )

    with pytest.raises(DBAPIError, match="legacy product graph ownership violation"):
        command.upgrade(config, "head")

    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0008_bitbucket_client_credentials"
        )
        assert (
            connection.execute(
                text("SELECT candidate_revision_id FROM products WHERE id = :product_id"),
                {"product_id": first_product_id},
            ).scalar_one()
            == second_revision_id
        )
    assert "display_name" not in {
        column["name"] for column in inspect(engine).get_columns("product_revisions")
    }


def _constraint_names(engine: Engine, table_name: str) -> set[str]:
    inspector = inspect(engine)
    names = {
        constraint["name"]
        for constraint in inspector.get_check_constraints(table_name)
        + inspector.get_foreign_keys(table_name)
        + inspector.get_unique_constraints(table_name)
        if constraint.get("name") is not None
    }
    primary_key = inspector.get_pk_constraint(table_name).get("name")
    if primary_key is not None:
        names.add(primary_key)
    return names


def _normalized_running_predicate(raw_predicate: str) -> str:
    return (
        raw_predicate.replace("::character varying", "")
        .replace("::text", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )


def _seed_preview_watchdog_rows(
    engine: Engine,
) -> tuple[datetime, tuple[UUID, ...], tuple[UUID, ...]]:
    """Seed every persisted state, including more than one watchdog batch."""
    product_id = uuid4()
    revision_id = uuid4()
    mapping_id = uuid4()
    cutoff = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    rows: list[dict[str, object]] = []

    for ordinal in range(125):
        rows.append(
            {
                "id": uuid4(),
                "input_digest": hashlib.sha256(f"running-{ordinal}".encode()).hexdigest(),
                "attempt": 1,
                "state": "running",
                "product_id": product_id,
                "revision_id": revision_id,
                "mapping_id": mapping_id,
                "started_at": cutoff - timedelta(hours=2, seconds=ordinal // 2),
                "finished_at": None,
                "result": None,
                "error_code": None,
            }
        )

    rows.append(
        {
            "id": uuid4(),
            "input_digest": hashlib.sha256(b"running-fresh").hexdigest(),
            "attempt": 1,
            "state": "running",
            "product_id": product_id,
            "revision_id": revision_id,
            "mapping_id": mapping_id,
            "started_at": cutoff + timedelta(seconds=1),
            "finished_at": None,
            "result": None,
            "error_code": None,
        }
    )
    for ordinal, state in enumerate(("queued", "succeeded", "failed", "timed_out"), 1):
        terminal = state in {"succeeded", "failed", "timed_out"}
        rows.append(
            {
                "id": uuid4(),
                "input_digest": hashlib.sha256(f"{state}-{ordinal}".encode()).hexdigest(),
                "attempt": 1,
                "state": state,
                "product_id": product_id,
                "revision_id": revision_id,
                "mapping_id": mapping_id,
                "started_at": None if state == "queued" else cutoff - timedelta(hours=4),
                "finished_at": cutoff if terminal else None,
                "result": '{"digest": "retained"}' if state == "succeeded" else None,
                "error_code": (
                    "processing_failed"
                    if state == "failed"
                    else "time_limit_exceeded"
                    if state == "timed_out"
                    else None
                ),
            }
        )

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO products (id, display_name, name_key) "
                "VALUES (:id, 'Watchdog Product', :name_key)"
            ),
            {"id": product_id, "name_key": f"watchdog-{product_id}"},
        )
        connection.execute(
            text(
                "INSERT INTO product_revisions "
                "(id, product_id, display_name, name_key, description, version, "
                "is_published, published_at) VALUES "
                "(:id, :product_id, 'Watchdog Product', :name_key, "
                "'candidate', 1, false, NULL)"
            ),
            {
                "id": revision_id,
                "product_id": product_id,
                "name_key": f"watchdog-{product_id}",
            },
        )
        connection.execute(
            text("UPDATE products SET candidate_revision_id = :revision_id WHERE id = :product_id"),
            {"revision_id": revision_id, "product_id": product_id},
        )
        connection.execute(
            text(
                "INSERT INTO product_repository_mappings "
                "(id, revision_id, topology, identity_key) "
                "VALUES (:id, :revision_id, 'direct', 'watchdog')"
            ),
            {"id": mapping_id, "revision_id": revision_id},
        )
        connection.execute(
            text(
                "INSERT INTO preview_jobs "
                "(id, input_digest, attempt, state, product_id, candidate_revision_id, "
                "candidate_revision_version, mapping_id, topology, connection_generation, "
                "detector_version, layout_identity, repository_sides, started_at, "
                "finished_at, result, error_code) VALUES "
                "(:id, :input_digest, :attempt, :state, :product_id, :revision_id, 1, "
                ":mapping_id, 'direct', 0, 'preview-v1', 'automatic', "
                "CAST('[]' AS jsonb), :started_at, :finished_at, "
                "CAST(:result AS jsonb), :error_code)"
            ),
            rows,
        )

    stale_running = tuple(
        cast(UUID, row["id"])
        for row in sorted(
            (
                row
                for row in rows
                if row["state"] == "running"
                and isinstance(row["started_at"], datetime)
                and row["started_at"] <= cutoff
            ),
            key=lambda row: (row["started_at"], row["id"]),
        )
    )
    return cutoff, tuple(cast(UUID, row["id"]) for row in rows), stale_running


def _preview_job_ids(engine: Engine) -> set[UUID]:
    with engine.connect() as connection:
        return set(connection.execute(text("SELECT id FROM preview_jobs")).scalars())


def _explain_index_names(explain: list[dict[str, object]]) -> set[str]:
    pending = [explain[0]["Plan"]]
    index_names: set[str] = set()
    while pending:
        node = pending.pop()
        assert isinstance(node, dict)
        index_name = node.get("Index Name")
        if isinstance(index_name, str):
            index_names.add(index_name)
        plans = node.get("Plans", [])
        assert isinstance(plans, list)
        pending.extend(plans)
    return index_names


def test_preview_watchdog_index_upgrade_downgrade_and_reupgrade_preserves_rows(
    migrated_database: tuple[Config, Engine],
) -> None:
    """Revision 0010 adds and removes only the running-preview access path."""
    config, engine = migrated_database
    command.upgrade(config, "0009_product_graph_integrity")
    _cutoff, expected_ids, _stale_running = _seed_preview_watchdog_rows(engine)

    indexes_before = {index["name"] for index in inspect(engine).get_indexes("preview_jobs")}
    constraints_before = _constraint_names(engine, "preview_jobs")
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("0010_preview_watchdog_index")
    assert revision is not None
    assert revision.down_revision == "0009_product_graph_integrity"

    command.upgrade(config, "0010_preview_watchdog_index")
    indexes_after = {index["name"] for index in inspect(engine).get_indexes("preview_jobs")}
    assert indexes_after - indexes_before == {PREVIEW_WATCHDOG_INDEX}
    watchdog_index = next(
        index
        for index in inspect(engine).get_indexes("preview_jobs")
        if index["name"] == PREVIEW_WATCHDOG_INDEX
    )
    assert watchdog_index["column_names"] == ["state", "started_at"]
    predicate = watchdog_index["dialect_options"]["postgresql_where"]
    assert _normalized_running_predicate(predicate) == "state = 'running'"

    preview_columns = {column["name"] for column in inspect(engine).get_columns("preview_jobs")}
    assert "task_id" not in preview_columns
    assert inspect(engine).get_pk_constraint("preview_jobs")["constrained_columns"] == ["id"]
    assert _preview_job_ids(engine) == set(expected_ids)

    command.downgrade(config, "0009_product_graph_integrity")
    assert {index["name"] for index in inspect(engine).get_indexes("preview_jobs")} == (
        indexes_before
    )
    assert _constraint_names(engine, "preview_jobs") == constraints_before
    assert _preview_job_ids(engine) == set(expected_ids)

    command.upgrade(config, "0010_preview_watchdog_index")
    assert {index["name"] for index in inspect(engine).get_indexes("preview_jobs")} == (
        indexes_after
    )
    assert _constraint_names(engine, "preview_jobs") == constraints_before
    assert _preview_job_ids(engine) == set(expected_ids)


def test_preview_job_identity_remains_uuid_without_task_id() -> None:
    """The existing PreviewJob UUID stays the sole durable Celery identity."""
    from verboflex.models.preview_job import PreviewJob

    watchdog_indexes = [
        index for index in PreviewJob.__table__.indexes if index.name == PREVIEW_WATCHDOG_INDEX
    ]
    assert len(watchdog_indexes) == 1
    watchdog_index = watchdog_indexes[0]
    assert [column.name for column in watchdog_index.expressions] == ["state", "started_at"]
    assert str(watchdog_index.dialect_options["postgresql"]["where"]) == "state = 'running'"
    assert list(PreviewJob.__table__.primary_key.columns.keys()) == ["id"]
    assert "task_id" not in PreviewJob.__table__.columns
    assert not hasattr(PreviewJob, "task_id")


def test_preview_watchdog_explain_reaches_partial_index_and_bounded_selector(
    migrated_database: tuple[Config, Engine],
) -> None:
    """The exact stale-running selector can reach the partial index without widening."""
    config, engine = migrated_database
    command.upgrade(config, "0009_product_graph_integrity")
    cutoff, expected_ids, stale_running = _seed_preview_watchdog_rows(engine)
    command.upgrade(config, "0010_preview_watchdog_index")

    selector = (
        "SELECT id, state, started_at FROM preview_jobs "
        "WHERE state = 'running' AND started_at <= :cutoff "
        "ORDER BY started_at, id LIMIT 100 FOR UPDATE SKIP LOCKED"
    )
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL enable_seqscan = off"))
        explain = connection.execute(
            text(f"EXPLAIN (FORMAT JSON, COSTS OFF) {selector}"),
            {"cutoff": cutoff},
        ).scalar_one()
        selected = connection.execute(text(selector), {"cutoff": cutoff}).all()

    assert PREVIEW_WATCHDOG_INDEX in _explain_index_names(explain)
    assert len(selected) == 100
    assert all(row.state == "running" and row.started_at <= cutoff for row in selected)
    assert tuple(row.id for row in selected) == stale_running[:100]
    with engine.connect() as connection:
        retained = connection.execute(text("SELECT id, state FROM preview_jobs ORDER BY id")).all()
    assert {row.id for row in retained} == set(expected_ids)
    assert {row.state for row in retained} == {
        "queued",
        "running",
        "succeeded",
        "failed",
        "timed_out",
    }


def test_active_revision_revalidation_sidecar_migrates_reversibly(
    migrated_database: tuple[Config, Engine],
) -> None:
    """Backfill candidate scope and remove/recreate only 0011-owned authority."""
    from verboflex import models

    config, engine = migrated_database
    command.upgrade(config, "0009_product_graph_integrity")
    _cutoff, expected_ids, _stale_running = _seed_preview_watchdog_rows(engine)
    command.upgrade(config, "0010_preview_watchdog_index")
    command.upgrade(config, "head")

    assert hasattr(models, "ActiveRevisionRevalidationConfirmation")
    inspector = inspect(engine)
    preview_columns = {column["name"]: column for column in inspector.get_columns("preview_jobs")}
    assert preview_columns["revision_scope"]["nullable"] is False
    assert {
        constraint["name"] for constraint in inspector.get_check_constraints("preview_jobs")
    } >= {"ck_preview_jobs_revision_scope_value"}
    assert {
        constraint["name"] for constraint in inspector.get_unique_constraints("preview_jobs")
    } >= {"uq_preview_jobs_id_revision_scope"}
    with engine.connect() as connection:
        scoped = connection.execute(
            text("SELECT id, revision_scope FROM preview_jobs ORDER BY id")
        ).all()
    assert {row.id for row in scoped} == set(expected_ids)
    assert {row.revision_scope for row in scoped} == {"candidate"}

    job_id = scoped[0].id
    actor_id = uuid4()
    layout_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, display_name, hashed_password) "
                "VALUES (:id, :email, 'Migration Revalidation Admin', 'not-a-secret')"
            ),
            {"id": actor_id, "email": f"migration-revalidation-{actor_id}@example.com"},
        )
        connection.execute(
            text(
                "UPDATE preview_jobs SET revision_scope = 'active_revalidation' WHERE id = :job_id"
            ),
            {"job_id": job_id},
        )
        authority = connection.execute(
            text(
                "SELECT product_id, candidate_revision_id, candidate_revision_version, "
                "mapping_id, connection_generation FROM preview_jobs WHERE id = :job_id"
            ),
            {"job_id": job_id},
        ).one()
        connection.execute(
            text(
                "INSERT INTO active_revision_revalidation_confirmations "
                "(job_id, revision_scope, product_id, revision_id, revision_version, "
                "mapping_id, connection_generation, preview_digest, layout_candidate_id, "
                "layout_candidate_version, confirmed_by, confirmed_at) VALUES "
                "(:job_id, 'active_revalidation', :product_id, :revision_id, "
                ":revision_version, :mapping_id, :generation, :digest, :layout_id, 1, "
                ":actor_id, CURRENT_TIMESTAMP)"
            ),
            {
                "job_id": job_id,
                "product_id": authority.product_id,
                "revision_id": authority.candidate_revision_id,
                "revision_version": authority.candidate_revision_version,
                "mapping_id": authority.mapping_id,
                "generation": authority.connection_generation,
                "digest": "d" * 64,
                "layout_id": layout_id,
                "actor_id": actor_id,
            },
        )

    with (
        pytest.raises(DBAPIError, match="revalidation confirmation is immutable"),
        engine.begin() as connection,
    ):
        connection.execute(
            text(
                "UPDATE active_revision_revalidation_confirmations "
                "SET preview_digest = :digest WHERE job_id = :job_id"
            ),
            {"digest": "e" * 64, "job_id": job_id},
        )

    command.downgrade(config, "0010_preview_watchdog_index")
    downgraded = inspect(engine)
    assert "active_revision_revalidation_confirmations" not in downgraded.get_table_names()
    assert "revision_scope" not in {
        column["name"] for column in downgraded.get_columns("preview_jobs")
    }
    assert _preview_job_ids(engine) == set(expected_ids)

    command.upgrade(config, "head")
    with engine.connect() as connection:
        reupgraded = connection.execute(
            text("SELECT id, revision_scope FROM preview_jobs ORDER BY id")
        ).all()
    assert {row.id for row in reupgraded} == set(expected_ids)
    assert {row.revision_scope for row in reupgraded} == {"candidate"}
