"""Real PostgreSQL work bounds; every write targets an owned disposable database."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

from alembic import command
from tests.api import test_translation_workspace as workspace_support
from verboflex.models.product import Product
from verboflex.models.translation import TranslationValue
from verboflex.models.user import User
from verboflex.schemas.translation_workspace import TranslationKeySearchQuery
from verboflex.services import translation_workspace as current

ROOT = Path(__file__).resolve().parents[3]
SECRET = "workspace-performance-test-secret-32-bytes"
PRINCIPAL = UUID("00000000-0000-0000-0000-000000000001")


@contextmanager
def owned_database(*, dump=None, postgres_container=None):
    """Never consult application settings or accept a caller's existing database."""
    admin_url = os.environ["VERBOFLEX_TEST_POSTGRES_ADMIN_URL"]
    name = "verboflex_workspace_perf_" + uuid4().hex
    with connect(admin_url, autocommit=True, connect_timeout=5) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = admin_url.rsplit("/", 1)[0] + "/" + name
    url = url.replace("postgresql://", "postgresql+psycopg://")
    engine = create_engine(
        url, connect_args={"connect_timeout": 5, "options": "-c statement_timeout=60000"}
    )
    try:
        if dump is not None:
            if not postgres_container:
                raise ValueError("a restore requires an explicit PostgreSQL container")
            # Only the generated database name is passed; credentials stay inside the container.
            with Path(dump).open("rb") as archive:
                restored = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "-i",
                        postgres_container,
                        "sh",
                        "-c",
                        "exec pg_restore --exit-on-error --no-owner --no-privileges "
                        '-U "$POSTGRES_USER" -d "$1"',
                        "restore",
                        name,
                    ],
                    stdin=archive,
                    capture_output=True,
                    timeout=180,
                )
            if restored.returncode:
                raise RuntimeError("disposable database restore failed; output withheld")
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        config = Config(ROOT / "backend/alembic.ini")
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("VERBOFLEX_DATABASE_URL", url)
            command.upgrade(config, "head")
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()
        with connect(admin_url, autocommit=True, connect_timeout=5) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def baseline_module(ref="9adf24c"):
    """Load a hash-pinned fixture, independent of private development history."""
    if ref not in {"9adf24c", "9adf24c4171eaf3e9168e486c1ed626f706aa259"}:
        raise ValueError("baseline must be the trusted 9adf24c revision")
    source = (
        ROOT / "backend/tests/fixtures/performance/translation_workspace_9adf24c.py.txt"
    ).read_bytes()
    if (
        hashlib.sha256(source).hexdigest()
        != "3573125465a8cb53fdc897358a0b916d2e2ae94d2cb2a0fdb24367a8b9898c52"
    ):
        raise ValueError("trusted workspace baseline fixture changed")
    module = ModuleType("workspace_trusted_baseline")
    exec(compile(source, "<trusted-workspace-baseline>", "exec"), module.__dict__)
    return module, hashlib.sha256(source).hexdigest()


def seed_historical(factory, count=100_000):
    """Reuse published-graph factories and bulk lawful inserts with all guards enabled."""
    product, scope, _ = workspace_support.seed_keys(factory)
    history, history_scope = workspace_support.SEARCH._seed_dataset(factory, name="History")
    value_id = workspace_support.SEARCH._add_group(
        factory,
        product_id=history,
        scope_id=history_scope,
        raw_key="historical-template",
        language="fr",
        values=(
            {"source_text": "Source", "translated_text": "History", "display_text": "History"},
        ),
    )
    with factory.begin() as session:
        for value in session.scalars(select(TranslationValue)):
            workspace_support.WORK.revision(session, value, source=value.source_text, number=1)
        session.flush()
        template = session.get_one(TranslationValue, value_id)
        session.execute(
            text(
                "CREATE TEMP TABLE performance_ids AS SELECT gen_random_uuid() AS key_id, "
                "gen_random_uuid() AS value_id, n FROM generate_series(1, :count) AS n"
            ),
            {"count": count},
        )
        overrides = {
            "translation_keys": (
                "id",
                template.translation_key_id,
                "'id', ids.key_id, 'raw_key', 'historical-' || ids.n",
            ),
            "translation_values": (
                "id",
                value_id,
                "'id', ids.value_id, 'translation_key_id', ids.key_id",
            ),
            "translation_value_revisions": (
                "value_id",
                value_id,
                "'id', gen_random_uuid(), 'value_id', ids.value_id, "
                "'translation_key_id', ids.key_id",
            ),
            "translation_value_locators": (
                "value_id",
                value_id,
                "'value_id', ids.value_id, 'translation_key_id', ids.key_id",
            ),
        }
        for table, (identity, template_id, changes) in overrides.items():
            columns = list(
                session.scalars(
                    text(
                        "SELECT attname FROM pg_attribute "
                        "WHERE attrelid = CAST(:table AS regclass) "
                        "AND attnum > 0 AND NOT attisdropped AND attgenerated = '' ORDER BY attnum"
                    ),
                    {"table": table},
                )
            )
            names = ", ".join('"' + column + '"' for column in columns)
            projections = ", ".join('copy."' + column + '"' for column in columns)
            session.execute(
                text(
                    f"INSERT INTO {table} ({names}) SELECT {projections} "
                    f"FROM {table} AS template CROSS JOIN performance_ids AS ids "
                    f"CROSS JOIN LATERAL jsonb_populate_record(NULL::{table}, "
                    f"to_jsonb(template) || jsonb_build_object({changes})) AS copy "
                    f"WHERE template.{identity} = :template_id"
                ),
                {"template_id": template_id},
            )
            # FK checks must not retain tiny-table sequential plans during bulk growth.
            session.execute(text(f"ANALYZE {table}"))
        actor = User(email="perf@example.com", display_name="Fixture", hashed_password="test-only")
        session.add(actor)
        session.flush()
        historical_product = session.get_one(Product, history)
        historical_product.is_active = False
        historical_product.deleted_at = session.scalar(text("SELECT now()"))
        historical_product.deleted_by = actor.id
    with factory.begin() as session:
        session.execute(text("ANALYZE"))
    return product, scope


def read_page(factory, module=current, **filters):
    with factory() as session:
        return module.search_translation_keys(
            session,
            principal_id=PRINCIPAL,
            query=TranslationKeySearchQuery(**filters),
            cursor_secret=SECRET,
        )


def semantic(page):
    return page.model_dump(mode="json", exclude={"next_cursor"})


def explain_metadata(factory, module, product_id):
    with factory() as session:
        session.execute(text("SET LOCAL jit = off"))
        return session.execute(
            text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + module._METADATA.text),
            {"product_id": product_id},
        ).scalar_one()[0]


def plan_nodes(node):
    yield node
    for child in node.get("Plans", []):
        yield from plan_nodes(child)


@pytest.fixture(scope="module")
def historical_factory():
    with owned_database() as factory:
        product, scope = seed_historical(factory)
        yield factory, product, scope


def test_metadata_preserves_languages_without_scanning_values_or_history(historical_factory):
    factory, product, _ = historical_factory
    baseline, _ = baseline_module()
    for product_id in (None, product):
        with factory() as session:
            expected = session.execute(baseline._METADATA, {"product_id": product_id}).one()
            actual = session.execute(current._METADATA, {"product_id": product_id}).one()
        assert actual.languages == expected.languages
        plan = explain_metadata(factory, current, product_id)
        scans = [
            node
            for node in plan_nodes(plan["Plan"])
            if node.get("Relation Name")
            in {"translation_values", "translation_value_revisions", "translation_proposals"}
        ]
        assert scans == []


def test_same_data_first_continuation_and_filtered_pages(historical_factory):
    factory, product, _ = historical_factory
    baseline, _ = baseline_module()
    for filters in (
        {},
        {"product_id": product},
        {"product_id": product, "q": "it 60", "language": "it", "state": "draft"},
        {"product_id": product, "visible_languages": ["en"], "language": "en"},
    ):
        expected = read_page(factory, baseline, **filters)
        actual = read_page(factory, **filters)
        assert semantic(actual) == semantic(expected)
        assert bool(actual.next_cursor) == bool(expected.next_cursor)
        if actual.next_cursor:
            assert semantic(read_page(factory, cursor=actual.next_cursor, **filters)) == semantic(
                read_page(factory, baseline, cursor=expected.next_cursor, **filters)
            )


@pytest.mark.parametrize("finish", ["commit", "rollback"])
def test_jit_is_local_to_the_read_transaction(historical_factory, finish):
    factory, product, _ = historical_factory
    engine = factory.kw["bind"]
    settings = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        if "AS authority" in statement:
            settings.append(connection.execute(text("SHOW jit")).scalar_one())

    with engine.connect() as connection:
        default = connection.execute(text("SHOW jit")).scalar_one()
        connection.rollback()
        event.listen(engine, "before_cursor_execute", observe)
        try:
            with factory(bind=connection) as session:
                current.search_translation_keys(
                    session,
                    principal_id=PRINCIPAL,
                    query=TranslationKeySearchQuery(product_id=product),
                    cursor_secret=SECRET,
                )
                getattr(session, finish)()
            assert settings == ["off"]
            assert connection.execute(text("SHOW jit")).scalar_one() == default
        finally:
            event.remove(engine, "before_cursor_execute", observe)


def test_active_corpus_metadata_and_browse_work_are_bounded():
    """Run with VERBOFLEX_SCALE_ROWS=1000000 for a local million-row experiment."""
    count = int(os.environ.get("VERBOFLEX_SCALE_ROWS", "10000"))
    assert 10000 <= count <= 10_000_000
    with owned_database() as factory:
        seed_historical(factory, count=count)
        with factory.begin() as session:
            session.execute(
                text("UPDATE products SET is_active=true, deleted_at=NULL, deleted_by=NULL")
            )
            session.execute(text("ANALYZE"))
        metadata = explain_metadata(factory, current, None)
        assert not any(
            node.get("Relation Name")
            in {
                "translation_values",
                "translation_keys",
                "translation_value_revisions",
                "translation_proposals",
            }
            for node in plan_nodes(metadata["Plan"])
        )
        statements = []

        def observe(connection, cursor, statement, parameters, context, executemany):
            if "browse_candidates AS MATERIALIZED" in statement:
                statements.append((statement, parameters))

        engine = factory.kw["bind"]
        event.listen(engine, "before_cursor_execute", observe)
        try:
            first = read_page(factory)
            second = read_page(factory, cursor=first.next_cursor)
        finally:
            event.remove(engine, "before_cursor_execute", observe)
        assert len(first.items) == len(second.items) == 50
        assert {item.translation_key_id for item in first.items}.isdisjoint(
            item.translation_key_id for item in second.items
        )
        plans = []
        with engine.connect() as connection:
            connection.exec_driver_sql("SET LOCAL jit=off")
            for statement, parameters in statements:
                plan = connection.exec_driver_sql(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters
                ).scalar_one()[0]
                key_scans = [
                    node
                    for node in plan_nodes(plan["Plan"])
                    if node.get("Relation Name") == "translation_keys"
                ]
                assert key_scans and all(node["Node Type"] != "Seq Scan" for node in key_scans)
                visited = sum(node["Actual Rows"] * node["Actual Loops"] for node in key_scans)
                assert visited < 1500, (count, visited)
                value_scans = [
                    node
                    for node in plan_nodes(plan["Plan"])
                    if node.get("Relation Name")
                    in {"translation_values", "translation_value_revisions"}
                ]
                values_visited = sum(
                    node["Actual Rows"] * node["Actual Loops"] for node in value_scans
                )
                assert values_visited < 10000, (count, values_visited)
                plans.append(
                    {
                        "execution_ms": plan["Execution Time"],
                        "keys_visited": visited,
                        "values_visited": values_visited,
                    }
                )
        print(
            json.dumps(
                {
                    "active_values": count + 184,
                    "metadata_ms": metadata["Execution Time"],
                    "pages": plans,
                }
            )
        )
