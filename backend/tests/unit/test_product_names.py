"""Executable A-01 and immutable candidate-revision contract."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from hypothesis import given
from hypothesis import strategies as st
from psycopg import connect, sql
from sqlalchemy import Engine, create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.services.products import (
    ProductNameConflict,
    ProductVersionConflict,
    create_product,
    normalize_product_name,
    save_product_candidate,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)


@pytest.fixture(scope="module")
def product_database() -> Iterator[tuple[sessionmaker[Session], Engine]]:
    """Migrate one disposable PostgreSQL database for the product contract."""
    database_name = f"verboflex_product_names_{uuid4().hex}"
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
        yield factory, engine
    finally:
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


@pytest.fixture(autouse=True)
def clean_products(product_database: tuple[sessionmaker[Session], Engine]) -> Iterator[None]:
    """Keep database-backed examples independent."""
    factory, engine = product_database
    if {"products", "product_revisions"} <= set(inspect(engine).get_table_names()):
        with factory.begin() as session:
            session.execute(text("TRUNCATE products CASCADE"))
    yield
    if {"products", "product_revisions"} <= set(inspect(engine).get_table_names()):
        with factory.begin() as session:
            session.execute(text("TRUNCATE products CASCADE"))


@pytest.mark.parametrize(
    ("raw_name", "expected_display", "expected_key"),
    [
        ("  VerboFlex\tMobile  ", "VerboFlex Mobile", "verboflex mobile"),
        ("Cafe\u0301", "Café", "café"),
        ("Ａpp", "App", "app"),
        ("Straße", "Straße", "strasse"),
    ],
)
def test_a01_normalizes_display_and_global_identity_key(
    raw_name: str,
    expected_display: str,
    expected_key: str,
) -> None:
    assert normalize_product_name(raw_name) == (expected_display, expected_key)


@pytest.mark.parametrize(
    "raw_name",
    ["", " \t\n ", "bad\x00name", "bad\x07name", "x" * 121],
)
def test_a01_rejects_empty_control_and_overlong_names(raw_name: str) -> None:
    with pytest.raises(ValueError, match="product name"):
        normalize_product_name(raw_name)


def test_a01_preserves_approved_distinctions() -> None:
    assert normalize_product_name("Café")[1] != normalize_product_name("Cafe")[1]
    assert normalize_product_name("Product-A")[1] != normalize_product_name("Product A")[1]


@given(
    st.text(
        alphabet=st.sampled_from(tuple("AaÉéＡ -_\t\n\u2003")),
        min_size=1,
        max_size=80,
    )
)
def test_a01_is_idempotent_for_every_accepted_name(raw_name: str) -> None:
    try:
        display, key = normalize_product_name(raw_name)
    except ValueError:
        return
    assert normalize_product_name(display) == (display, key)


def test_product_schema_registers_global_identity_and_revision_guards(
    product_database: tuple[sessionmaker[Session], Engine],
) -> None:
    _factory, engine = product_database
    inspector = inspect(engine)
    assert {"products", "product_revisions"} <= set(inspector.get_table_names())
    assert {column["name"] for column in inspector.get_columns("products")} == {
        "id",
        "display_name",
        "name_key",
        "is_active",
        "active_revision_id",
        "candidate_revision_id",
        "created_at",
        "updated_at",
        "deleted_at",
        "deleted_by",
    }
    assert {column["name"] for column in inspector.get_columns("product_revisions")} == {
        "id",
        "product_id",
        "display_name",
        "name_key",
        "description",
        "version",
        "is_published",
        "published_at",
        "created_at",
        "updated_at",
    }
    product_indexes = {index["name"] for index in inspector.get_indexes("products")}
    assert "uq_products_live_name_key" in product_indexes
    foreign_keys = {
        foreign_key["name"]: (
            foreign_key["constrained_columns"],
            (foreign_key.get("options") or {}).get("ondelete"),
        )
        for foreign_key in inspector.get_foreign_keys("products")
    }
    assert foreign_keys == {
        "fk_products_active_owned_revision": (["id", "active_revision_id"], "RESTRICT"),
        "fk_products_candidate_owned_revision": (
            ["id", "candidate_revision_id"],
            "RESTRICT",
        ),
        "fk_products_deleted_by_users": (["deleted_by"], "RESTRICT"),
    }
    revision_foreign_key = inspector.get_foreign_keys("product_revisions")[0]
    assert revision_foreign_key["constrained_columns"] == ["product_id"]
    assert (revision_foreign_key.get("options") or {}).get("ondelete") == "CASCADE"

    with engine.connect() as connection:
        trigger_count = connection.execute(
            text(
                "SELECT count(*) FROM pg_trigger "
                "WHERE tgname = 'trg_guard_active_product_revisions' "
                "AND NOT tgisinternal"
            )
        ).scalar_one()
    assert trigger_count == 1


def test_product_uuid_remains_identity_while_a01_name_key_is_globally_unique(
    product_database: tuple[sessionmaker[Session], Engine],
) -> None:
    factory, _engine = product_database
    first = create_product(
        factory(),
        name="  VerboFlex\tMobile ",
        description=None,
    )
    assert isinstance(first.id, UUID)
    assert first.display_name == "VerboFlex Mobile"
    assert first.name_key == "verboflex mobile"

    with pytest.raises(ProductNameConflict):
        create_product(
            factory(),
            name="verboflex mobile",
            description="duplicate",
        )

    with factory() as session:
        from verboflex.models.product import Product

        assert len(session.scalars(select(Product)).all()) == 1


def _publish_initial_candidate(
    factory: sessionmaker[Session], product_id: UUID
) -> tuple[UUID, int]:
    """Promote the initial candidate only to establish the Task 2 active fixture."""
    from verboflex.models.product import Product, ProductRevision

    with factory.begin() as session:
        product = session.get(Product, product_id)
        assert product is not None
        assert product.candidate_revision_id is not None
        revision = session.get(ProductRevision, product.candidate_revision_id)
        assert revision is not None
        revision.is_published = True
        revision.published_at = datetime.now(UTC)
        session.flush()
        product.active_revision_id = revision.id
        product.candidate_revision_id = None
        product.is_active = True
        session.flush()
        return revision.id, revision.version


def _product_graph(factory: sessionmaker[Session], product_id: UUID) -> tuple[object, ...]:
    from verboflex.models.product import Product, ProductRevision

    with factory() as session:
        product = session.get(Product, product_id)
        assert product is not None
        revisions = tuple(
            session.execute(
                select(
                    ProductRevision.id,
                    ProductRevision.display_name,
                    ProductRevision.name_key,
                    ProductRevision.description,
                    ProductRevision.version,
                    ProductRevision.is_published,
                )
                .where(ProductRevision.product_id == product_id)
                .order_by(ProductRevision.id)
            ).all()
        )
        return (
            product.display_name,
            product.name_key,
            product.active_revision_id,
            product.candidate_revision_id,
            product.is_active,
            revisions,
        )


def test_active_revision_is_immutable_and_stale_candidate_writes_roll_back(
    product_database: tuple[sessionmaker[Session], Engine],
) -> None:
    from verboflex.models.product import ProductRevision

    factory, _engine = product_database
    product = create_product(
        factory(),
        name="Desktop",
        description="published description",
    )
    active_id, active_version = _publish_initial_candidate(factory, product.id)

    updated = save_product_candidate(
        factory(),
        product_id=product.id,
        expected_version=active_version,
        name="Desktop",
        description="candidate description",
    )
    assert updated.active_revision_id == active_id
    assert updated.candidate_revision_id is not None
    assert updated.candidate_revision_id != active_id

    with factory() as session:
        active = session.get(ProductRevision, active_id)
        candidate = session.get(ProductRevision, updated.candidate_revision_id)
        assert active is not None and candidate is not None
        assert active.description == "published description"
        assert active.display_name == "Desktop"
        assert active.name_key == "desktop"
        assert active.is_published is True
        assert active.version == active_version
        assert candidate.description == "candidate description"
        assert candidate.display_name == "Desktop"
        assert candidate.name_key == "desktop"
        assert candidate.is_published is False
        assert candidate.version == active_version + 1

    before_conflict = _product_graph(factory, product.id)
    with pytest.raises(ProductVersionConflict):
        save_product_candidate(
            factory(),
            product_id=product.id,
            expected_version=active_version,
            name="Desktop stale writer",
            description="must roll back",
        )
    assert _product_graph(factory, product.id) == before_conflict

    with (
        pytest.raises(Exception, match="active product revision graph is immutable"),
        factory.begin() as session,
    ):
        active = session.get(ProductRevision, active_id)
        assert active is not None
        active.description = "forbidden mutation"
        session.flush()
