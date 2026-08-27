"""Atomic product publication and operational lifecycle contracts."""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from types import ModuleType
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)


@pytest.fixture(scope="module")
def publication_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for publication race proofs."""
    database_name = f"verboflex_product_publication_{uuid4().hex}"
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


def _publication_module() -> ModuleType:
    try:
        return importlib.import_module("verboflex.services.publication")
    except ModuleNotFoundError as error:
        pytest.fail(f"publication service must exist: {error}")


def _add_mapping(
    session: Session,
    *,
    revision_id: UUID,
    repository_id: UUID,
    state: str,
) -> UUID:
    mapping_id = uuid4()
    mapping = ProductRepositoryMapping(
        id=mapping_id,
        revision_id=revision_id,
        topology="direct",
        identity_key=f'["direct","{repository_id}","main"]',
        selected_layout_candidate_id=(None if state == "layout_missing" else uuid4()),
        selected_layout_version=(None if state == "layout_missing" else 1),
    )
    if state != "mapping_invalid":
        mapping.sides = [
            ProductMappingRepositorySide(
                role="direct",
                repository_id=repository_id,
                source_branch="main",
            )
        ]
    if state == "target_invalid":
        mapping.allowed_targets = [
            ProductMappingAllowedTarget(branch="release/1", is_default=False)
        ]
    else:
        mapping.allowed_targets = [ProductMappingAllowedTarget(branch="release/1", is_default=True)]
    session.add(mapping)
    return mapping_id


def _seed_product_graph(
    factory: sessionmaker[Session],
    *,
    candidate_mapping_state: str = "valid",
    include_candidate: bool = True,
    is_active: bool = True,
) -> tuple[UUID, UUID, UUID | None, UUID]:
    """Create published configuration and an optional candidate graph."""
    product_id = uuid4()
    active_id = uuid4()
    candidate_id = uuid4() if include_candidate else None
    repository_id = uuid4()
    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=f"Product {product_id}",
            name_key=f"product {product_id}",
            is_active=is_active,
        )
        session.add(product)
        session.flush()
        session.add(
            ProductRevision(
                id=active_id,
                product_id=product_id,
                description="published",
                version=6,
                is_published=True,
                published_at=datetime.now(UTC),
            )
        )
        if candidate_id is not None:
            session.add(
                ProductRevision(
                    id=candidate_id,
                    product_id=product_id,
                    description="candidate",
                    version=7,
                    is_published=False,
                )
            )
        session.add(
            Repository(
                id=repository_id,
                workspace="publication-team",
                repository_slug=f"repo-{repository_id.hex[:12]}",
            )
        )
        session.flush()
        _add_mapping(
            session,
            revision_id=active_id,
            repository_id=repository_id,
            state="valid",
        )
        if candidate_id is not None and candidate_mapping_state != "missing":
            _add_mapping(
                session,
                revision_id=candidate_id,
                repository_id=repository_id,
                state=candidate_mapping_state,
            )
        session.flush()
        product.active_revision_id = active_id
        product.candidate_revision_id = candidate_id
    return product_id, active_id, candidate_id, repository_id


def _graph_snapshot(
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
) -> tuple[tuple[Any, ...], ...]:
    """Capture every durable field publication is allowed to affect."""
    with factory() as session:
        product = session.execute(
            select(
                Product.id,
                Product.is_active,
                Product.active_revision_id,
                Product.candidate_revision_id,
                Product.display_name,
                Product.name_key,
            ).where(Product.id == product_id)
        ).one()
        revisions = tuple(
            session.execute(
                select(
                    ProductRevision.id,
                    ProductRevision.version,
                    ProductRevision.description,
                    ProductRevision.is_published,
                    ProductRevision.published_at,
                )
                .where(ProductRevision.product_id == product_id)
                .order_by(ProductRevision.id)
            ).all()
        )
        revision_ids = tuple(revision.id for revision in revisions)
        mappings = tuple(
            session.execute(
                select(
                    ProductRepositoryMapping.id,
                    ProductRepositoryMapping.revision_id,
                    ProductRepositoryMapping.topology,
                    ProductRepositoryMapping.identity_key,
                    ProductRepositoryMapping.selected_layout_candidate_id,
                    ProductRepositoryMapping.selected_layout_version,
                )
                .where(ProductRepositoryMapping.revision_id.in_(revision_ids))
                .order_by(ProductRepositoryMapping.id)
            ).all()
        )
        mapping_ids = tuple(mapping.id for mapping in mappings)
        sides = tuple(
            session.execute(
                select(
                    ProductMappingRepositorySide.mapping_id,
                    ProductMappingRepositorySide.role,
                    ProductMappingRepositorySide.repository_id,
                    ProductMappingRepositorySide.source_branch,
                )
                .where(ProductMappingRepositorySide.mapping_id.in_(mapping_ids))
                .order_by(
                    ProductMappingRepositorySide.mapping_id,
                    ProductMappingRepositorySide.role,
                )
            ).all()
        )
        targets = tuple(
            session.execute(
                select(
                    ProductMappingAllowedTarget.mapping_id,
                    ProductMappingAllowedTarget.branch,
                    ProductMappingAllowedTarget.is_default,
                )
                .where(ProductMappingAllowedTarget.mapping_id.in_(mapping_ids))
                .order_by(
                    ProductMappingAllowedTarget.mapping_id,
                    ProductMappingAllowedTarget.branch,
                )
            ).all()
        )
    return (tuple(product), revisions, mappings, sides, targets)


def _always_confirmed(
    _session: Session,
    _revision: ProductRevision,
    _mapping: ProductRepositoryMapping,
) -> bool:
    return True


def test_product_lock_linearizes_publish_equal_retry_and_stale_writer(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """Two sessions produce one pointer swap and one idempotent equal retry."""
    publication = _publication_module()
    product_id, old_active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory
    )
    assert candidate_id is not None
    barrier = Barrier(2)
    confirmation_calls: list[UUID] = []

    def confirm_once(
        _session: Session,
        _revision: ProductRevision,
        mapping: ProductRepositoryMapping,
    ) -> bool:
        confirmation_calls.append(mapping.id)
        return True

    def publish_once(_index: int) -> bool:
        with publication_session_factory() as session:
            barrier.wait()
            result = publication.publish_product_candidate(
                session,
                product_id=product_id,
                candidate_revision_id=candidate_id,
                expected_candidate_version=7,
                confirmation_predicate=confirm_once,
            )
            return result.changed

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(publish_once, range(2)))

    assert sorted(results) == [False, True]
    assert len(confirmation_calls) == 1
    with publication_session_factory() as session:
        product = session.get_one(Product, product_id)
        published = session.get_one(ProductRevision, candidate_id)
        prior = session.get_one(ProductRevision, old_active_id)
        assert product.active_revision_id == candidate_id
        assert product.candidate_revision_id is None
        assert product.is_active is True
        assert published.is_published is True
        assert published.published_at is not None
        assert published.version == 7
        assert prior.is_published is True

    winner_snapshot = _graph_snapshot(publication_session_factory, product_id=product_id)
    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationConflict, match="revision conflict"),
    ):
        publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=6,
            confirmation_predicate=_always_confirmed,
        )
    assert _graph_snapshot(publication_session_factory, product_id=product_id) == winner_snapshot
    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationConflict, match="revision conflict"),
    ):
        publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=old_active_id,
            expected_candidate_version=6,
            confirmation_predicate=_always_confirmed,
        )
    assert _graph_snapshot(publication_session_factory, product_id=product_id) == winner_snapshot


@pytest.mark.parametrize(
    ("mapping_state", "expected_blocker"),
    (
        ("missing", "mappings_required"),
        ("mapping_invalid", "mapping_configuration_invalid"),
        ("target_invalid", "target_configuration_invalid"),
        ("layout_missing", "layout_required"),
        ("valid", "preview_confirmation_required"),
    ),
)
def test_closed_blockers_leave_active_and_candidate_graphs_unchanged(
    publication_session_factory: sessionmaker[Session],
    mapping_state: str,
    expected_blocker: str,
) -> None:
    """Every incomplete candidate fails closed before pointer or graph mutation."""
    publication = _publication_module()
    product_id, _active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory,
        candidate_mapping_state=mapping_state,
    )
    assert candidate_id is not None
    before = _graph_snapshot(publication_session_factory, product_id=product_id)

    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationBlocked) as blocked,
    ):
        publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=7,
        )

    assert tuple(blocker.value for blocker in blocked.value.blockers) == (expected_blocker,)
    assert tuple(blocker.value for blocker in publication.PublicationBlocker) == (
        "mappings_required",
        "mapping_configuration_invalid",
        "target_configuration_invalid",
        "layout_required",
        "preview_confirmation_required",
    )
    assert _graph_snapshot(publication_session_factory, product_id=product_id) == before


def test_deactivate_retains_configuration_and_reactivate_reuses_publication_predicate(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """Operational suspension changes only Product state and cannot bypass preview."""
    publication = _publication_module()
    product_id, active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory,
        candidate_mapping_state="valid",
    )
    assert candidate_id is not None
    before = _graph_snapshot(publication_session_factory, product_id=product_id)

    with publication_session_factory() as session:
        deactivated = publication.deactivate_product(session, product_id=product_id)
    after_deactivate = _graph_snapshot(publication_session_factory, product_id=product_id)
    assert deactivated.changed is True
    assert after_deactivate[0][1] is False
    assert after_deactivate[0][2:] == before[0][2:]
    assert after_deactivate[1:] == before[1:]

    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationBlocked) as blocked,
    ):
        publication.reactivate_product(
            session,
            product_id=product_id,
            active_revision_id=active_id,
            expected_active_version=6,
        )
    assert tuple(blocker.value for blocker in blocked.value.blockers) == (
        "preview_confirmation_required",
    )
    assert _graph_snapshot(publication_session_factory, product_id=product_id) == after_deactivate

    with publication_session_factory() as session:
        reactivated = publication.reactivate_product(
            session,
            product_id=product_id,
            active_revision_id=active_id,
            expected_active_version=6,
            confirmation_predicate=_always_confirmed,
        )
    after_reactivate = _graph_snapshot(publication_session_factory, product_id=product_id)
    assert reactivated.changed is True
    assert after_reactivate[0][1] is True
    assert after_reactivate[0][2:] == before[0][2:]
    assert after_reactivate[1:] == before[1:]

    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationConflict, match="revision conflict"),
    ):
        publication.reactivate_product(
            session,
            product_id=product_id,
            active_revision_id=uuid4(),
            expected_active_version=6,
            confirmation_predicate=_always_confirmed,
        )
    assert _graph_snapshot(publication_session_factory, product_id=product_id) == after_reactivate


def test_publication_closed_structure_and_corruption_guards(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """Malformed durable topology and missing revision identities fail closed."""
    publication = _publication_module()
    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationConflict, match="revision conflict"),
    ):
        publication._locked_revision(session, uuid4())

    keys_repository_id = uuid4()
    translations_repository_id = uuid4()

    def separate_mapping(*, roles: tuple[str, ...], same_repository: bool = False) -> Any:
        mapping = ProductRepositoryMapping(
            revision_id=uuid4(),
            topology="separate",
            identity_key=f"separate-{uuid4()}",
        )
        mapping.sides = [
            ProductMappingRepositorySide(
                role=role,
                repository_id=(
                    keys_repository_id
                    if same_repository or role == "keys"
                    else translations_repository_id
                ),
                source_branch="main",
            )
            for role in roles
        ]
        return mapping

    assert publication._mapping_structure_is_valid(separate_mapping(roles=("keys", "translations")))
    assert not publication._mapping_structure_is_valid(
        separate_mapping(roles=("keys", "translations"), same_repository=True)
    )
    assert not publication._mapping_structure_is_valid(separate_mapping(roles=("keys",)))
    unsupported = separate_mapping(roles=("keys", "translations"))
    unsupported.topology = "unsupported"
    assert not publication._mapping_structure_is_valid(unsupported)
