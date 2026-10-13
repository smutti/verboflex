"""Isolated PostgreSQL contract for the durable review workspace schema."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.translation import LocalizationScope, TranslationKey, TranslationValue
from verboflex.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
EXPECTED_HEAD = "0046_screenshots"
REVIEW_TABLES = {
    "translation_proposals",
    "translation_proposal_values",
    "review_activities",
    "translation_comments",
    "translation_comment_versions",
    "translation_comment_mentions",
    "notifications",
}


@dataclass(frozen=True)
class ReviewDatabase:
    config: Config
    engine: Engine
    ids: dict[str, UUID]
    prior_snapshot: dict[str, object]


def _schema_missing(assertion_id: str, detail: object) -> None:
    pytest.fail(f"PHASE5_SCHEMA_MISSING[{assertion_id}]: {detail}")


def _current_revision(connection: Connection) -> str:
    return str(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one())


def _selector_digest(selector_bytes: bytes) -> str:
    return hashlib.sha256(selector_bytes).hexdigest()


def _seed_prior_data(engine: Engine) -> dict[str, UUID]:
    ids = {
        "actor": uuid4(),
        "recipient": uuid4(),
        "product": uuid4(),
        "revision": uuid4(),
        "repository": uuid4(),
        "mapping": uuid4(),
        "scope": uuid4(),
        "key": uuid4(),
        "value": uuid4(),
    }
    selector = b'{"kind":"scalar","schema_version":1}'
    with Session(engine) as session, session.begin():
        product = Product(
            id=ids["product"],
            display_name=f"Review schema {ids['product']}",
            name_key=f"review schema {ids['product']}",
            is_active=True,
        )
        session.add(product)
        session.flush()
        session.add_all(
            [
                ProductRevision(
                    id=ids["revision"],
                    product_id=ids["product"],
                    description="review schema prior row",
                    version=1,
                    is_published=False,
                ),
                Repository(
                    id=ids["repository"],
                    workspace="review-schema",
                    repository_slug=f"repo-{ids['repository'].hex}",
                    descriptive_name="Review schema repository",
                    descriptive_name_key="review schema repository",
                ),
                User(
                    id=ids["actor"],
                    email=f"review-actor-{ids['actor']}@example.com",
                    display_name="Review schema actor",
                    hashed_password="not-used",
                    is_active=True,
                    must_change_password=False,
                ),
                User(
                    id=ids["recipient"],
                    email=f"review-recipient-{ids['recipient']}@example.com",
                    display_name="Review schema recipient",
                    hashed_password="not-used",
                    is_active=True,
                    must_change_password=False,
                ),
            ]
        )
        session.flush()
        identity_key = f'[["direct","{ids["repository"]}","main"]]'
        session.add(
            ProductRepositoryMapping(
                id=ids["mapping"],
                revision_id=ids["revision"],
                topology="direct",
                identity_key=identity_key,
                base_language="en",
                sides=[
                    ProductMappingRepositorySide(
                        role="direct",
                        repository_id=ids["repository"],
                        source_branch="main",
                    )
                ],
                allowed_targets=[ProductMappingAllowedTarget(branch="main", is_default=True)],
            )
        )
        session.flush()
        revision = session.get_one(ProductRevision, ids["revision"])
        revision.is_published = True
        revision.published_at = datetime.now(UTC)
        session.flush()
        product.active_revision_id = ids["revision"]
        session.flush()
        session.add(
            LocalizationScope(
                id=ids["scope"],
                product_id=ids["product"],
                mapping_identity_key=identity_key,
                current_revision_id=ids["revision"],
                current_mapping_id=ids["mapping"],
            )
        )
        session.flush()
        session.add(
            TranslationKey(
                id=ids["key"],
                scope_id=ids["scope"],
                product_id=ids["product"],
                repository_id=ids["repository"],
                configured_branch="main",
                raw_key="review.welcome",
            )
        )
        session.flush()
        session.add(
            TranslationValue(
                id=ids["value"],
                scope_id=ids["scope"],
                translation_key_id=ids["key"],
                language="it",
                selector_version=1,
                selector_kind="scalar",
                selector_bytes=selector,
                selector_digest=_selector_digest(selector),
                source_text="Hello",
                translated_text="Ciao",
                display_text="Ciao",
                structure=[],
                review_state="approved",
            )
        )
    return ids


def _metadata_snapshot(engine: Engine) -> dict[str, object]:
    inspector = inspect(engine)
    tables = tuple(sorted(inspector.get_table_names(schema="public")))
    schema: dict[str, object] = {}
    for table_name in tables:
        schema[table_name] = {
            "columns": tuple(
                sorted(
                    (
                        column["name"],
                        str(column["type"]),
                        bool(column["nullable"]),
                        str(column.get("default")),
                    )
                    for column in inspector.get_columns(table_name)
                )
            ),
            "checks": tuple(
                sorted(
                    (item["name"], item["sqltext"])
                    for item in inspector.get_check_constraints(table_name)
                )
            ),
            "foreign_keys": tuple(
                sorted(
                    (
                        item["name"],
                        tuple(item["constrained_columns"]),
                        item["referred_table"],
                        tuple(item["referred_columns"]),
                    )
                    for item in inspector.get_foreign_keys(table_name)
                )
            ),
            "indexes": tuple(
                sorted(
                    (item["name"], tuple(item["column_names"]), bool(item["unique"]))
                    for item in inspector.get_indexes(table_name)
                )
            ),
            "uniques": tuple(
                sorted(
                    (item["name"], tuple(item["column_names"]))
                    for item in inspector.get_unique_constraints(table_name)
                )
            ),
        }
    return {"tables": tables, "schema": schema}


def _data_snapshot(engine: Engine, ids: dict[str, UUID]) -> tuple[tuple[object, ...], ...]:
    statements = (
        (
            "products",
            "SELECT id, display_name, active_revision_id FROM products WHERE id = :id",
            ids["product"],
        ),
        (
            "users",
            "SELECT id, email, display_name, is_active FROM users "
            "WHERE id IN (:actor, :recipient) ORDER BY id",
            None,
        ),
        (
            "localization_scopes",
            "SELECT id, product_id, dataset_version FROM localization_scopes WHERE id = :id",
            ids["scope"],
        ),
        (
            "translation_keys",
            "SELECT id, scope_id, raw_key, is_deleted FROM translation_keys WHERE id = :id",
            ids["key"],
        ),
        (
            "translation_values",
            "SELECT id, translation_key_id, language, display_text, review_state "
            "FROM translation_values WHERE id = :id",
            ids["value"],
        ),
    )
    rows: list[tuple[object, ...]] = []
    with engine.connect() as connection:
        for table_name, statement, row_id in statements:
            parameters: dict[str, object]
            if table_name == "users":
                parameters = {"actor": ids["actor"], "recipient": ids["recipient"]}
            else:
                parameters = {"id": row_id}
            for row in connection.execute(text(statement), parameters):
                rows.append((table_name, *(str(value) for value in row)))
    return tuple(rows)


@pytest.fixture(scope="module")
def review_database() -> Iterator[ReviewDatabase]:
    database_name = f"verboflex_review_workspace_{uuid4().hex}"
    with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
        admin_connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )
    database_url = ADMIN_DATABASE_URL.rsplit("/", 1)[0] + f"/{database_name}"
    sqlalchemy_url = database_url.replace("postgresql://", "postgresql+psycopg://")
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlalchemy_url)
    engine = create_engine(sqlalchemy_url)
    # Seed with the current ORM, then exercise the historical schema using raw SQL.
    command.upgrade(config, "head")
    ids = _seed_prior_data(engine)
    command.downgrade(config, "0027_xliff_format")
    prior_snapshot = {
        "metadata": _metadata_snapshot(engine),
        "data": _data_snapshot(engine, ids),
    }
    command.upgrade(config, "head")
    try:
        yield ReviewDatabase(config=config, engine=engine, ids=ids, prior_snapshot=prior_snapshot)
    finally:
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def _constraint_names(engine: Engine, table_name: str) -> set[str]:
    inspector = inspect(engine)
    return {
        *(item["name"] for item in inspector.get_check_constraints(table_name)),
        *(item["name"] for item in inspector.get_foreign_keys(table_name)),
        *(item["name"] for item in inspector.get_unique_constraints(table_name)),
    }


def _trigger_names(engine: Engine) -> set[str]:
    with engine.connect() as connection:
        return set(
            connection.scalars(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgrelid::regclass::text = ANY(:tables)"
                ),
                {"tables": sorted(REVIEW_TABLES)},
            )
        )


@pytest.mark.parametrize(
    ("assertion_id", "expected"),
    [
        ("review-tables", REVIEW_TABLES),
        (
            "proposal-key-language",
            {
                "uq_translation_proposals_key_language",
                "fk_translation_proposals_owned_key",
                "ck_translation_proposals_language_normalized",
            },
        ),
        (
            "proposal-version-basis-state",
            {
                "ck_translation_proposals_version_range",
                "ck_translation_proposals_state_value",
                "ck_translation_proposal_values_basis_revision_non_negative",
                "ck_translation_proposal_values_basis_digest_sha256",
            },
        ),
        (
            "proposal-selector-ownership",
            {
                "fk_translation_proposal_values_owned_proposal",
                "fk_translation_proposal_values_imported_value",
                "uq_translation_proposal_values_proposal_selector",
            },
        ),
        (
            "comment-key-language",
            {
                "fk_translation_comments_owned_key",
                "ck_translation_comments_language_normalized",
                "fk_translation_comment_versions_owned_comment",
            },
        ),
        (
            "immutable-evidence-triggers",
            {
                "trg_review_activities_append_only",
                "trg_translation_comment_versions_immutable",
                "trg_translation_comment_mentions_immutable",
            },
        ),
        (
            "notification-recipient-comment-kind",
            {
                "uq_notifications_recipient_comment_kind",
                "ck_notifications_kind_value",
                "fk_notifications_recipient",
                "fk_notifications_originating_comment",
            },
        ),
        (
            "deterministic-indexes",
            {
                "ix_review_activities_proposal_created",
                "ix_translation_comments_key_language_created",
                "ix_notifications_recipient_unread_created",
            },
        ),
    ],
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_review_workspace_schema_invariant(
    review_database: ReviewDatabase,
    assertion_id: str,
    expected: set[str],
) -> None:
    with review_database.engine.connect() as connection:
        revision = _current_revision(connection)
    if revision != EXPECTED_HEAD:
        _schema_missing(assertion_id, f"expected revision {EXPECTED_HEAD}, found {revision}")
    inspector = inspect(review_database.engine)
    if assertion_id == "review-tables":
        missing = expected - set(inspector.get_table_names())
    elif assertion_id == "proposal-key-language":
        missing = expected - _constraint_names(review_database.engine, "translation_proposals")
    elif assertion_id == "proposal-version-basis-state":
        actual = _constraint_names(
            review_database.engine, "translation_proposals"
        ) | _constraint_names(review_database.engine, "translation_proposal_values")
        missing = expected - actual
    elif assertion_id == "proposal-selector-ownership":
        missing = expected - _constraint_names(
            review_database.engine, "translation_proposal_values"
        )
    elif assertion_id == "comment-key-language":
        actual = _constraint_names(
            review_database.engine, "translation_comments"
        ) | _constraint_names(review_database.engine, "translation_comment_versions")
        missing = expected - actual
    elif assertion_id == "immutable-evidence-triggers":
        missing = expected - _trigger_names(review_database.engine)
    elif assertion_id == "notification-recipient-comment-kind":
        missing = expected - _constraint_names(review_database.engine, "notifications")
    else:
        actual_indexes = {
            item["name"]
            for table_name in REVIEW_TABLES
            for item in inspector.get_indexes(table_name)
        }
        missing = expected - actual_indexes
    if missing:
        _schema_missing(assertion_id, f"missing {sorted(missing)}")


def _expect_rejected(connection: Connection, statement: str, parameters: dict[str, Any]) -> None:
    savepoint = connection.begin_nested()
    with pytest.raises((IntegrityError, DBAPIError)):
        connection.execute(text(statement), parameters)
    savepoint.rollback()


def test_review_workspace_database_invariants(review_database: ReviewDatabase) -> None:
    ids = review_database.ids
    proposal_id = uuid4()
    activity_id = uuid4()
    comment_id = uuid4()
    version_id = uuid4()
    mention_id = uuid4()
    notification_id = uuid4()
    selector_digest = _selector_digest(b'{"kind":"scalar","schema_version":1}')
    with review_database.engine.connect() as connection, connection.begin():
        if _current_revision(connection) != EXPECTED_HEAD:
            _schema_missing("database-invariants", "review migration is not installed")
        connection.execute(
            text(
                "INSERT INTO translation_proposals "
                "(id, scope_id, translation_key_id, language, version, state, "
                "reconciliation_required, created_by, updated_by) "
                "VALUES (:id, :scope, :key, 'it', 1, 'draft', false, :actor, :actor)"
            ),
            {"id": proposal_id, "scope": ids["scope"], "key": ids["key"], "actor": ids["actor"]},
        )
        connection.execute(
            text(
                "INSERT INTO translation_proposal_values "
                "(id, proposal_id, translation_key_id, language, translation_value_id, "
                "selector_version, selector_digest, basis_revision_number, basis_digest, "
                "proposed_text, grapheme_count) "
                "VALUES (:id, :proposal, :key, 'it', :value, 1, :selector, 0, :basis, '', 0)"
            ),
            {
                "id": uuid4(),
                "proposal": proposal_id,
                "key": ids["key"],
                "value": ids["value"],
                "selector": selector_digest,
                "basis": "a" * 64,
            },
        )
        connection.execute(
            text(
                "INSERT INTO review_activities "
                "(id, proposal_id, translation_key_id, language, kind, proposal_version, "
                "to_state, actor_id) "
                "VALUES (:id, :proposal, :key, 'it', 'proposal_saved', 1, 'draft', :actor)"
            ),
            {"id": activity_id, "proposal": proposal_id, "key": ids["key"], "actor": ids["actor"]},
        )
        connection.execute(
            text(
                "INSERT INTO translation_comments "
                "(id, scope_id, translation_key_id, language, author_id, current_version) "
                "VALUES (:id, :scope, :key, 'it', :actor, 1)"
            ),
            {"id": comment_id, "scope": ids["scope"], "key": ids["key"], "actor": ids["actor"]},
        )
        connection.execute(
            text(
                "INSERT INTO translation_comment_versions "
                "(id, comment_id, translation_key_id, language, version_number, body, author_id) "
                "VALUES (:id, :comment, :key, 'it', 1, '@Recipient review', :actor)"
            ),
            {"id": version_id, "comment": comment_id, "key": ids["key"], "actor": ids["actor"]},
        )
        connection.execute(
            text(
                "INSERT INTO translation_comment_mentions "
                "(id, comment_version_id, mentioned_user_id, start_utf16, end_utf16, display_text) "
                "VALUES (:id, :version, :recipient, 0, 10, '@Recipient')"
            ),
            {"id": mention_id, "version": version_id, "recipient": ids["recipient"]},
        )
        connection.execute(
            text(
                "INSERT INTO notifications "
                "(id, recipient_user_id, actor_user_id, originating_comment_id, kind) "
                "VALUES (:id, :recipient, :actor, :comment, 'mention')"
            ),
            {
                "id": notification_id,
                "recipient": ids["recipient"],
                "actor": ids["actor"],
                "comment": comment_id,
            },
        )

        _expect_rejected(
            connection,
            "UPDATE translation_proposals SET state = 'reconciliation' WHERE id = :id",
            {"id": proposal_id},
        )
        _expect_rejected(
            connection,
            "UPDATE translation_proposals SET version = -1 WHERE id = :id",
            {"id": proposal_id},
        )
        _expect_rejected(
            connection,
            "UPDATE translation_proposal_values SET basis_revision_number = -1 "
            "WHERE proposal_id = :id",
            {"id": proposal_id},
        )
        _expect_rejected(
            connection,
            "UPDATE translation_proposal_values SET basis_digest = 'bad' WHERE proposal_id = :id",
            {"id": proposal_id},
        )
        for table_name, row_id in (
            ("review_activities", activity_id),
            ("translation_comment_versions", version_id),
            ("translation_comment_mentions", mention_id),
        ):
            _expect_rejected(
                connection,
                f"UPDATE {table_name} SET id = id WHERE id = :id",
                {"id": row_id},
            )
            _expect_rejected(connection, f"DELETE FROM {table_name} WHERE id = :id", {"id": row_id})
        _expect_rejected(
            connection,
            "INSERT INTO notifications "
            "(id, recipient_user_id, actor_user_id, originating_comment_id, kind) "
            "VALUES (:id, :recipient, :actor, :comment, 'mention')",
            {
                "id": uuid4(),
                "recipient": ids["recipient"],
                "actor": ids["actor"],
                "comment": comment_id,
            },
        )
        assert (
            connection.execute(
                text("SELECT reconciliation_required FROM translation_proposals WHERE id = :id"),
                {"id": proposal_id},
            ).scalar_one()
            is False
        )
        assert (
            connection.execute(
                text("SELECT review_state FROM translation_values WHERE id = :id"),
                {"id": ids["value"]},
            ).scalar_one()
            == "approved"
        )


def test_review_workspace_migration_round_trip_preserves_prior_schema_and_data(
    review_database: ReviewDatabase,
) -> None:
    with review_database.engine.connect() as connection:
        if _current_revision(connection) != EXPECTED_HEAD:
            _schema_missing("migration-round-trip", "review migration is not installed")
    command.downgrade(review_database.config, "0027_xliff_format")
    assert _metadata_snapshot(review_database.engine) == review_database.prior_snapshot["metadata"]
    assert (
        _data_snapshot(review_database.engine, review_database.ids)
        == review_database.prior_snapshot["data"]
    )
    command.upgrade(review_database.config, "head")
    with review_database.engine.connect() as connection:
        assert _current_revision(connection) == EXPECTED_HEAD
