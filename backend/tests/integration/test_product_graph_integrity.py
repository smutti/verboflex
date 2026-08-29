"""PostgreSQL ownership and published product-graph immutability contracts."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)


@pytest.fixture(scope="module")
def graph_engine() -> Iterator[Engine]:
    """Migrate one isolated PostgreSQL database for adversarial SQL."""
    database_name = f"verboflex_product_graph_{uuid4().hex}"
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

    try:
        yield engine
    finally:
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def _seed_graph(engine: Engine) -> dict[str, Any]:
    identities = {
        name: uuid4()
        for name in (
            "product",
            "foreign_product",
            "active_revision",
            "candidate_revision",
            "foreign_revision",
            "active_mapping",
            "candidate_mapping",
            "foreign_mapping",
            "repository",
            "foreign_repository",
            "actor",
            "candidate_job",
        )
    }
    identities.update(
        {
            "product_display_name": f"Owned {identities['product']}",
            "product_name_key": f"owned {identities['product']}",
            "candidate_display_name": f"Candidate {identities['candidate_revision']}",
            "candidate_name_key": f"candidate {identities['candidate_revision']}",
            "foreign_display_name": f"Foreign {identities['foreign_product']}",
            "foreign_name_key": f"foreign {identities['foreign_product']}",
            "candidate_digest": identities["candidate_job"].hex * 2,
        }
    )
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, email, display_name, hashed_password) "
                "VALUES (:actor, :email, 'Graph Admin', 'not-a-secret')"
            ),
            {
                "actor": identities["actor"],
                "email": f"graph-{identities['actor']}@example.com",
            },
        )
        connection.execute(
            text(
                "INSERT INTO products (id, display_name, name_key, is_active) VALUES "
                "(:product, :product_display_name, :product_name_key, true), "
                "(:foreign_product, :foreign_display_name, :foreign_name_key, true)"
            ),
            identities,
        )
        has_revision_identity = connection.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'product_revisions' "
                "AND column_name = 'display_name')"
            )
        ).scalar_one()
        if has_revision_identity:
            connection.execute(
                text(
                    "INSERT INTO product_revisions "
                    "(id, product_id, display_name, name_key, description, version, "
                    "is_published, published_at) VALUES "
                    "(:active_revision, :product, :product_display_name, :product_name_key, "
                    "'active', 4, false, NULL), "
                    "(:candidate_revision, :product, :candidate_display_name, "
                    ":candidate_name_key, "
                    "'candidate', 5, false, NULL), "
                    "(:foreign_revision, :foreign_product, :foreign_display_name, "
                    ":foreign_name_key, 'foreign', 2, false, NULL)"
                ),
                {**identities, "now": now},
            )
        else:
            connection.execute(
                text(
                    "INSERT INTO product_revisions "
                    "(id, product_id, description, version, is_published, published_at) "
                    "VALUES "
                    "(:active_revision, :product, 'active', 4, false, NULL), "
                    "(:candidate_revision, :product, 'candidate', 5, false, NULL), "
                    "(:foreign_revision, :foreign_product, 'foreign', 2, false, NULL)"
                ),
                {**identities, "now": now},
            )
        connection.execute(
            text(
                "INSERT INTO repositories (id, workspace, repository_slug) VALUES "
                "(:repository, 'graph-team', :repository_slug), "
                "(:foreign_repository, 'foreign-team', :foreign_slug)"
            ),
            {
                **identities,
                "repository_slug": f"repo-{identities['repository'].hex}",
                "foreign_slug": f"repo-{identities['foreign_repository'].hex}",
            },
        )
        connection.execute(
            text(
                "INSERT INTO product_repository_mappings "
                "(id, revision_id, topology, identity_key, "
                "selected_layout_candidate_id, selected_layout_version) VALUES "
                "(:active_mapping, :active_revision, 'direct', 'active', "
                ":active_layout, 1), "
                "(:candidate_mapping, :candidate_revision, 'direct', 'candidate', "
                ":candidate_layout, 1), "
                "(:foreign_mapping, :foreign_revision, 'direct', 'foreign', "
                ":foreign_layout, 1)"
            ),
            {
                **identities,
                "active_layout": uuid4(),
                "candidate_layout": uuid4(),
                "foreign_layout": uuid4(),
            },
        )
        for prefix in ("active", "candidate", "foreign"):
            connection.execute(
                text(
                    "INSERT INTO product_mapping_repository_sides "
                    "(mapping_id, role, repository_id, source_branch) "
                    "VALUES (:mapping_id, 'direct', :repository_id, 'main')"
                ),
                {
                    "mapping_id": identities[f"{prefix}_mapping"],
                    "repository_id": (
                        identities["foreign_repository"]
                        if prefix == "foreign"
                        else identities["repository"]
                    ),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO product_mapping_allowed_targets "
                    "(mapping_id, branch, is_default) "
                    "VALUES (:mapping_id, 'release/1', true)"
                ),
                {"mapping_id": identities[f"{prefix}_mapping"]},
            )
        connection.execute(
            text(
                "UPDATE product_revisions SET is_published = true, published_at = :now "
                "WHERE id IN (:active_revision, :foreign_revision)"
            ),
            {**identities, "now": now},
        )
        connection.execute(
            text(
                "UPDATE products SET active_revision_id = :active_revision, "
                "candidate_revision_id = :candidate_revision WHERE id = :product"
            ),
            identities,
        )
        connection.execute(
            text(
                "UPDATE products SET active_revision_id = :foreign_revision "
                "WHERE id = :foreign_product"
            ),
            identities,
        )
        connection.execute(
            text(
                "INSERT INTO preview_jobs "
                "(id, input_digest, attempt, state, product_id, "
                "candidate_revision_id, candidate_revision_version, mapping_id, "
                "topology, connection_generation, detector_version, layout_identity, "
                "repository_sides) VALUES "
                "(:candidate_job, :digest, 1, 'queued', :product, "
                ":candidate_revision, 5, :candidate_mapping, 'direct', 0, "
                "'preview-v1', 'auto', CAST('[]' AS jsonb))"
            ),
            {**identities, "digest": identities["candidate_digest"]},
        )
    return identities


def _expect_integrity_error(
    engine: Engine,
    statement: str,
    parameters: dict[str, Any],
) -> None:
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(statement), parameters)


def _expect_immutable(
    engine: Engine,
    statement: str,
    parameters: dict[str, Any],
) -> None:
    with (
        pytest.raises(DBAPIError, match="active product revision graph is immutable"),
        engine.begin() as connection,
    ):
        connection.execute(text(statement), parameters)


def test_database_rejects_every_cross_graph_reference(graph_engine: Engine) -> None:
    """Product pointers and preview identities cannot cross ownership graphs."""
    ids = _seed_graph(graph_engine)

    _expect_integrity_error(
        graph_engine,
        "UPDATE products SET active_revision_id = :foreign_revision WHERE id = :product",
        ids,
    )
    _expect_integrity_error(
        graph_engine,
        "UPDATE products SET candidate_revision_id = :foreign_revision WHERE id = :product",
        ids,
    )
    _expect_integrity_error(
        graph_engine,
        "INSERT INTO preview_jobs "
        "(id, input_digest, attempt, state, product_id, candidate_revision_id, "
        "candidate_revision_version, mapping_id, topology, connection_generation, "
        "detector_version, layout_identity, repository_sides) VALUES "
        "(:job_id, :digest, 1, 'queued', :foreign_product, :candidate_revision, "
        "5, :candidate_mapping, 'direct', 0, 'preview-v1', 'auto', CAST('[]' AS jsonb))",
        {**ids, "job_id": uuid4(), "digest": "b" * 64},
    )
    _expect_integrity_error(
        graph_engine,
        "INSERT INTO preview_jobs "
        "(id, input_digest, attempt, state, product_id, candidate_revision_id, "
        "candidate_revision_version, mapping_id, topology, connection_generation, "
        "detector_version, layout_identity, repository_sides) VALUES "
        "(:job_id, :digest, 1, 'queued', :product, :candidate_revision, "
        "5, :foreign_mapping, 'direct', 0, 'preview-v1', 'auto', CAST('[]' AS jsonb))",
        {**ids, "job_id": uuid4(), "digest": "c" * 64},
    )


def test_published_graph_is_immutable_but_candidate_graph_remains_editable(
    graph_engine: Engine,
) -> None:
    """Every root, side, target, layout, and confirmation write is guarded."""
    ids = _seed_graph(graph_engine)

    for statement in (
        "UPDATE product_revisions SET description = 'tampered' WHERE id = :active_revision",
        "UPDATE product_revisions SET display_name = 'Tampered', name_key = 'tampered' "
        "WHERE id = :active_revision",
        "DELETE FROM product_revisions WHERE id = :active_revision",
        "UPDATE product_repository_mappings SET identity_key = 'tampered' "
        "WHERE id = :active_mapping",
        "UPDATE product_repository_mappings SET selected_layout_candidate_id = :new_id, "
        "selected_layout_version = 2 WHERE id = :active_mapping",
        "UPDATE product_repository_mappings SET confirmed_preview_job_id = :candidate_job, "
        "confirmed_preview_digest = :digest, preview_confirmed_by = :actor, "
        "preview_confirmed_at = CURRENT_TIMESTAMP WHERE id = :active_mapping",
        "INSERT INTO product_repository_mappings "
        "(id, revision_id, topology, identity_key) VALUES "
        "(:new_id, :active_revision, 'direct', 'insert-tamper')",
        "UPDATE product_mapping_repository_sides SET source_branch = 'tampered' "
        "WHERE mapping_id = :active_mapping AND role = 'direct'",
        "DELETE FROM product_mapping_repository_sides "
        "WHERE mapping_id = :active_mapping AND role = 'direct'",
        "INSERT INTO product_mapping_repository_sides "
        "(mapping_id, role, repository_id, source_branch) VALUES "
        "(:active_mapping, 'keys', :repository, 'main')",
        "UPDATE product_mapping_allowed_targets SET is_default = false "
        "WHERE mapping_id = :active_mapping AND branch = 'release/1'",
        "DELETE FROM product_mapping_allowed_targets "
        "WHERE mapping_id = :active_mapping AND branch = 'release/1'",
        "INSERT INTO product_mapping_allowed_targets "
        "(mapping_id, branch, is_default) VALUES "
        "(:active_mapping, 'release/2', false)",
    ):
        _expect_immutable(
            graph_engine,
            statement,
            {**ids, "new_id": uuid4(), "digest": ids["candidate_digest"]},
        )

    temporary_mapping_id = uuid4()
    with graph_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE product_revisions SET display_name = :display_name, "
                "name_key = :name_key WHERE id = :candidate_revision"
            ),
            {
                **ids,
                "display_name": f"Edited {ids['candidate_revision']}",
                "name_key": f"edited {ids['candidate_revision']}",
            },
        )
        connection.execute(
            text(
                "UPDATE product_revisions SET description = 'candidate edited' "
                "WHERE id = :candidate_revision"
            ),
            ids,
        )
        connection.execute(
            text(
                "UPDATE product_repository_mappings SET identity_key = 'candidate edited', "
                "selected_layout_candidate_id = :new_layout, selected_layout_version = 2 "
                "WHERE id = :candidate_mapping"
            ),
            {**ids, "new_layout": uuid4()},
        )
        connection.execute(
            text(
                "INSERT INTO product_repository_mappings "
                "(id, revision_id, topology, identity_key) VALUES "
                "(:new_mapping, :candidate_revision, 'direct', 'candidate temporary')"
            ),
            {**ids, "new_mapping": temporary_mapping_id},
        )
        connection.execute(
            text(
                "UPDATE product_mapping_repository_sides SET source_branch = 'develop' "
                "WHERE mapping_id = :candidate_mapping AND role = 'direct'"
            ),
            ids,
        )
        connection.execute(
            text(
                "INSERT INTO product_mapping_repository_sides "
                "(mapping_id, role, repository_id, source_branch) VALUES "
                "(:candidate_mapping, 'keys', :repository, 'main')"
            ),
            ids,
        )
        connection.execute(
            text(
                "INSERT INTO product_mapping_allowed_targets "
                "(mapping_id, branch, is_default) VALUES "
                "(:candidate_mapping, 'release/2', false)"
            ),
            ids,
        )
        connection.execute(
            text(
                "UPDATE product_repository_mappings SET "
                "confirmed_preview_job_id = :candidate_job, "
                "confirmed_preview_digest = :digest, preview_confirmed_by = :actor, "
                "preview_confirmed_at = CURRENT_TIMESTAMP "
                "WHERE id = :candidate_mapping"
            ),
            {**ids, "digest": ids["candidate_digest"]},
        )
        connection.execute(
            text(
                "DELETE FROM product_mapping_repository_sides "
                "WHERE mapping_id = :candidate_mapping AND role = 'keys'"
            ),
            ids,
        )
        connection.execute(
            text("DELETE FROM product_repository_mappings WHERE id = :mapping_id"),
            {"mapping_id": temporary_mapping_id},
        )
        connection.execute(
            text(
                "DELETE FROM product_mapping_allowed_targets "
                "WHERE mapping_id = :candidate_mapping AND branch = 'release/2'"
            ),
            ids,
        )


def test_publication_order_needs_no_bypass_and_both_published_graphs_stay_immutable(
    graph_engine: Engine,
) -> None:
    """Metadata-before-pointer publication works without weakening another graph."""
    ids = _seed_graph(graph_engine)

    with graph_engine.connect() as connection:
        function_definition = connection.execute(
            text(
                "SELECT pg_get_functiondef(oid) FROM pg_proc "
                "WHERE proname = 'verboflex_guard_active_revision_child'"
            )
        ).scalar_one()
    lowered_definition = function_definition.lower()
    assert "current_setting" not in lowered_definition
    assert "set_config" not in lowered_definition
    assert "bypass" not in lowered_definition

    _expect_immutable(
        graph_engine,
        "UPDATE product_mapping_repository_sides SET source_branch = 'blocked-before' "
        "WHERE mapping_id = :active_mapping AND role = 'direct'",
        ids,
    )

    with graph_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE product_revisions SET is_published = true, "
                "published_at = CURRENT_TIMESTAMP WHERE id = :candidate_revision"
            ),
            ids,
        )
        connection.execute(
            text(
                "UPDATE products SET active_revision_id = :candidate_revision, "
                "candidate_revision_id = NULL WHERE id = :product"
            ),
            ids,
        )

    _expect_immutable(
        graph_engine,
        "UPDATE product_mapping_repository_sides SET source_branch = 'blocked-new' "
        "WHERE mapping_id = :candidate_mapping AND role = 'direct'",
        ids,
    )
    _expect_immutable(
        graph_engine,
        "UPDATE product_mapping_repository_sides SET source_branch = 'blocked-old' "
        "WHERE mapping_id = :active_mapping AND role = 'direct'",
        ids,
    )
