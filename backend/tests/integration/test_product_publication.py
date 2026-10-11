"""Atomic product publication and operational lifecycle contracts."""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from types import ModuleType
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from alembic import command
from verboflex.auth.passwords import hash_password
from verboflex.localization.preview.core import build_layout_candidate
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.preview_job import PreviewJob
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.user import User
from verboflex.services.preview_jobs import (
    PREVIEW_DETECTOR_VERSION,
    PREVIEW_LAYOUT_IDENTITY,
    _canonical_identity,
    _closed_result,
    _complete_preview_digest,
    _complete_sides,
    _identity,
    confirm_active_revision_revalidation,
    create_or_reuse_active_revision_revalidation_job,
    create_or_reuse_preview_job,
    execute_preview_job,
    get_active_revision_revalidation_job,
)
from verboflex.services.products import save_product_candidate

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
    base_language: str | None = "en",
) -> UUID:
    mapping_id = uuid4()
    mapping = ProductRepositoryMapping(
        id=mapping_id,
        revision_id=revision_id,
        topology="direct",
        identity_key=f'["direct","{repository_id}","main"]',
        base_language=base_language,
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
    candidate_mapping_count: int = 1,
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
        active_revision = ProductRevision(
            id=active_id,
            product_id=product_id,
            display_name=f"Product {product_id}",
            name_key=f"product {product_id}",
            description="published",
            version=6,
            is_published=False,
        )
        session.add(active_revision)
        if candidate_id is not None:
            session.add(
                ProductRevision(
                    id=candidate_id,
                    product_id=product_id,
                    display_name=f"Candidate {product_id}",
                    name_key=f"candidate {product_id}",
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
            for index in range(candidate_mapping_count):
                candidate_repository_id = repository_id if index == 0 else uuid4()
                if index > 0:
                    session.add(
                        Repository(
                            id=candidate_repository_id,
                            workspace="publication-team",
                            repository_slug=f"repo-{candidate_repository_id.hex[:12]}",
                        )
                    )
                    session.flush()
                _add_mapping(
                    session,
                    revision_id=candidate_id,
                    repository_id=candidate_repository_id,
                    state=candidate_mapping_state,
                )
        session.flush()
        active_revision.is_published = True
        active_revision.published_at = datetime.now(UTC)
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
                    ProductRevision.display_name,
                    ProductRevision.name_key,
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
                    ProductRepositoryMapping.base_language,
                    ProductRepositoryMapping.confirmed_preview_job_id,
                    ProductRepositoryMapping.confirmed_preview_digest,
                    ProductRepositoryMapping.preview_confirmed_by,
                    ProductRepositoryMapping.preview_confirmed_at,
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


def test_revision_insert_snapshots_only_each_missing_identity_component(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """Legacy construction fills either absent identity field without replacing its peer."""
    product_id = uuid4()
    display_only_id = uuid4()
    key_only_id = uuid4()
    with publication_session_factory.begin() as session:
        session.add(
            Product(
                id=product_id,
                display_name="Canonical Product",
                name_key="canonical product",
                is_active=False,
            )
        )
        session.flush()
        session.add_all(
            [
                ProductRevision(
                    id=display_only_id,
                    product_id=product_id,
                    display_name=None,
                    name_key="preserved-key",
                    description="display snapshot",
                ),
                ProductRevision(
                    id=key_only_id,
                    product_id=product_id,
                    display_name="Preserved Display",
                    name_key=None,
                    description="key snapshot",
                ),
            ]
        )
    with publication_session_factory() as session:
        display_only = session.get_one(ProductRevision, display_only_id)
        key_only = session.get_one(ProductRevision, key_only_id)
        assert (display_only.display_name, display_only.name_key) == (
            "Canonical Product",
            "preserved-key",
        )
        assert (key_only.display_name, key_only.name_key) == (
            "Preserved Display",
            "canonical product",
        )


def _preview_candidate(
    mapping_id: UUID,
    *,
    repository_side: str = "direct",
    languages: tuple[str, ...] = ("en",),
) -> dict[str, object]:
    return build_layout_candidate(
        repository_side=repository_side,
        format="json",
        layout_identity=f"locales/{mapping_id}/{{locale}}.json",
        files=tuple(f"locales/{mapping_id}/{language}.json" for language in languages),
        values={language: {"hello": f"Hello ({language})"} for language in languages},
    ).to_mapping()


def _confirm_revision_mappings(
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
    revision_id: UUID,
    mapping_ids: set[UUID] | None = None,
) -> tuple[UUID, ...]:
    """Persist exact succeeded jobs and current confirmations for selected mappings."""
    actor_id = uuid4()
    now = datetime.now(UTC)
    confirmed_jobs: list[UUID] = []
    with factory.begin() as session:
        session.add(
            User(
                id=actor_id,
                email=f"publication-{actor_id}@example.com",
                display_name="Publication Admin",
                hashed_password=hash_password("publication test password phrase!"),
                is_active=True,
                must_change_password=False,
            )
        )
        connection = session.get_one(BitbucketConnection, 1)
        connection.generation = 7
        connection.access_token_ciphertext = "encrypted-access"
        connection.refresh_token_ciphertext = None
        connection.scope_profile = "pullrequest:write"
        connection.provider_expires_at = now + timedelta(hours=1)
        connection.connected_at = now
        connection.revoked_at = None
        revision = session.get_one(ProductRevision, revision_id)
        mappings = tuple(
            session.execute(
                select(ProductRepositoryMapping)
                .options(selectinload(ProductRepositoryMapping.sides))
                .where(ProductRepositoryMapping.revision_id == revision_id)
                .order_by(ProductRepositoryMapping.id)
            ).scalars()
        )
        for mapping in mappings:
            if mapping_ids is not None and mapping.id not in mapping_ids:
                continue
            assert mapping.base_language is not None
            commits = {side.role: "a" * 40 for side in mapping.sides}
            repository_sides = _complete_sides(mapping, commits)
            _encoded, input_digest = _canonical_identity(
                product_id=product_id,
                revision=revision,
                mapping=mapping,
                connection_generation=connection.generation,
                repository_sides=repository_sides,
            )
            job = PreviewJob(
                id=uuid4(),
                input_digest=input_digest,
                attempt=1,
                state="succeeded",
                revision_scope="candidate",
                product_id=product_id,
                candidate_revision_id=revision_id,
                candidate_revision_version=revision.version,
                mapping_id=mapping.id,
                topology=mapping.topology,
                connection_generation=connection.generation,
                detector_version=PREVIEW_DETECTOR_VERSION,
                layout_identity=PREVIEW_LAYOUT_IDENTITY,
                repository_sides=repository_sides,
                result={},
                started_at=now,
                finished_at=now,
            )
            candidate = _preview_candidate(
                mapping.id,
                repository_side=("direct" if mapping.topology == "direct" else "translations"),
                languages=(mapping.base_language,),
            )
            job.result = _closed_result(
                _identity(job),
                {
                    "detector_version": PREVIEW_DETECTOR_VERSION,
                    "digest": input_digest,
                    "layout_candidates": [candidate],
                },
            )
            session.add(job)
            mapping.selected_layout_candidate_id = UUID(str(candidate["id"]))
            mapping.selected_layout_version = 1
            mapping.confirmed_preview_job_id = job.id
            mapping.confirmed_preview_digest = _complete_preview_digest(
                _identity(job),
                [candidate],
                base_language=mapping.base_language,
            )
            mapping.preview_confirmed_by = actor_id
            mapping.preview_confirmed_at = now
            confirmed_jobs.append(job.id)
    return tuple(confirmed_jobs)


def _always_confirmed(
    _session: Session,
    _revision: ProductRevision,
    _mapping: ProductRepositoryMapping,
) -> bool:
    return True


def _seed_published_base_language_graph(
    factory: sessionmaker[Session],
    *,
    mappings: tuple[tuple[str, str | None], ...],
) -> tuple[UUID, UUID]:
    """Create one published graph with exact direct/separate language authority."""
    product_id = uuid4()
    active_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=f"Base Language Product {product_id}",
            name_key=f"base language product {product_id}",
            is_active=True,
        )
        revision = ProductRevision(
            id=active_id,
            product_id=product_id,
            display_name=product.display_name,
            name_key=product.name_key,
            description="published base-language graph",
            version=6,
            is_published=False,
        )
        session.add(product)
        session.flush()
        session.add(revision)
        session.flush()

        for index, (topology, base_language) in enumerate(mappings):
            repository_ids = (uuid4(),) if topology == "direct" else (uuid4(), uuid4())
            for repository_id in repository_ids:
                session.add(
                    Repository(
                        id=repository_id,
                        workspace="base-language-publication",
                        repository_slug=f"repo-{repository_id.hex[:12]}",
                    )
                )
            session.flush()
            mapping_id = uuid4()
            roles = ("direct",) if topology == "direct" else ("keys", "translations")
            mapping = ProductRepositoryMapping(
                id=mapping_id,
                revision_id=active_id,
                topology=topology,
                identity_key=f"base-language-{index}-{topology}",
                base_language=base_language,
                selected_layout_candidate_id=uuid4(),
                selected_layout_version=1,
                sides=[
                    ProductMappingRepositorySide(
                        role=role,
                        repository_id=repository_ids[side_index],
                        source_branch="main" if role != "translations" else "translations",
                    )
                    for side_index, role in enumerate(roles)
                ],
                allowed_targets=[
                    ProductMappingAllowedTarget(
                        branch=f"release/{index}",
                        is_default=True,
                    )
                ],
            )
            session.add(mapping)
        session.flush()
        revision.is_published = True
        revision.published_at = now
        session.flush()
        product.active_revision_id = active_id
    return product_id, active_id


def _revision_graph_snapshot(
    factory: sessionmaker[Session],
    *,
    revision_id: UUID,
) -> tuple[object, ...]:
    """Capture one immutable revision and its complete mapping authority."""
    with factory() as session:
        revision = session.execute(
            select(
                ProductRevision.id,
                ProductRevision.product_id,
                ProductRevision.display_name,
                ProductRevision.name_key,
                ProductRevision.description,
                ProductRevision.version,
                ProductRevision.is_published,
                ProductRevision.published_at,
            ).where(ProductRevision.id == revision_id)
        ).one()
        mapping_rows = tuple(
            session.execute(
                select(
                    ProductRepositoryMapping.id,
                    ProductRepositoryMapping.revision_id,
                    ProductRepositoryMapping.topology,
                    ProductRepositoryMapping.identity_key,
                    ProductRepositoryMapping.base_language,
                    ProductRepositoryMapping.selected_layout_candidate_id,
                    ProductRepositoryMapping.selected_layout_version,
                    ProductRepositoryMapping.confirmed_preview_job_id,
                    ProductRepositoryMapping.confirmed_preview_digest,
                    ProductRepositoryMapping.preview_confirmed_by,
                    ProductRepositoryMapping.preview_confirmed_at,
                )
                .where(ProductRepositoryMapping.revision_id == revision_id)
                .order_by(ProductRepositoryMapping.identity_key)
            ).all()
        )
        mapping_ids = tuple(row.id for row in mapping_rows)
        side_rows = tuple(
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
        target_rows = tuple(
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
    return (tuple(revision), mapping_rows, side_rows, target_rows)


def test_base_language_clone_publication_and_noop_preserve_exact_direct_and_separate_values(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """Clone and publish exact languages while leaving the prior graph byte-equal."""
    publication = _publication_module()
    product_id, old_active_id = _seed_published_base_language_graph(
        publication_session_factory,
        mappings=(("direct", "en-US"), ("separate", "zh-Hant")),
    )
    old_active_before = _revision_graph_snapshot(
        publication_session_factory,
        revision_id=old_active_id,
    )

    with publication_session_factory() as session:
        saved = save_product_candidate(
            session,
            product_id=product_id,
            expected_version=6,
            name="Base Language Candidate",
            description="candidate graph",
            actor_id=None,
        )
        candidate_id = saved.candidate_revision_id
    assert candidate_id is not None

    with publication_session_factory() as session:
        candidate_mappings = tuple(
            session.execute(
                select(ProductRepositoryMapping)
                .where(ProductRepositoryMapping.revision_id == candidate_id)
                .order_by(ProductRepositoryMapping.identity_key)
            ).scalars()
        )
        assert [(mapping.topology, mapping.base_language) for mapping in candidate_mappings] == [
            ("direct", "en-US"),
            ("separate", "zh-Hant"),
        ]
        assert all(mapping.confirmed_preview_job_id is None for mapping in candidate_mappings)

    _confirm_revision_mappings(
        publication_session_factory,
        product_id=product_id,
        revision_id=candidate_id,
    )
    with publication_session_factory() as session:
        first = publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=7,
            actor_id=None,
        )
    assert first.changed is True
    assert (
        _revision_graph_snapshot(
            publication_session_factory,
            revision_id=old_active_id,
        )
        == old_active_before
    )

    published_before_retry = _revision_graph_snapshot(
        publication_session_factory,
        revision_id=candidate_id,
    )
    with publication_session_factory() as session:
        repeated = publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=7,
            actor_id=None,
        )
    assert repeated.changed is False
    assert repeated.active_revision_id == candidate_id
    assert repeated.candidate_revision_id is None
    assert (
        _revision_graph_snapshot(
            publication_session_factory,
            revision_id=candidate_id,
        )
        == published_before_retry
    )


def test_base_language_change_invalidates_confirmation_without_mutating_published_history(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """A candidate language edit makes its prior exact confirmation stale atomically."""
    publication = _publication_module()
    product_id, old_active_id = _seed_published_base_language_graph(
        publication_session_factory,
        mappings=(("direct", "en-US"), ("separate", "zh-Hant")),
    )
    old_active_before = _revision_graph_snapshot(
        publication_session_factory,
        revision_id=old_active_id,
    )
    with publication_session_factory() as session:
        saved = save_product_candidate(
            session,
            product_id=product_id,
            expected_version=6,
            name="Stale Language Candidate",
            description="candidate graph",
            actor_id=None,
        )
        candidate_id = saved.candidate_revision_id
    assert candidate_id is not None
    _confirm_revision_mappings(
        publication_session_factory,
        product_id=product_id,
        revision_id=candidate_id,
    )
    with publication_session_factory.begin() as session:
        mapping = session.scalar(
            select(ProductRepositoryMapping).where(
                ProductRepositoryMapping.revision_id == candidate_id,
                ProductRepositoryMapping.topology == "separate",
            )
        )
        assert mapping is not None
        mapping.base_language = "fr"
    before_rejected_publish = _graph_snapshot(
        publication_session_factory,
        product_id=product_id,
    )

    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationBlocked) as blocked,
    ):
        publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=7,
            actor_id=None,
        )

    assert tuple(blocker.value for blocker in blocked.value.blockers) == (
        "preview_confirmation_required",
    )
    assert (
        _graph_snapshot(
            publication_session_factory,
            product_id=product_id,
        )
        == before_rejected_publish
    )
    assert (
        _revision_graph_snapshot(
            publication_session_factory,
            revision_id=old_active_id,
        )
        == old_active_before
    )


def test_base_language_legacy_null_clone_stays_null_and_cannot_publish_without_confirmation(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """Legacy nullable authority is cloned exactly and never defaults to a locale."""
    publication = _publication_module()
    product_id, old_active_id = _seed_published_base_language_graph(
        publication_session_factory,
        mappings=(("direct", None),),
    )
    old_active_before = _revision_graph_snapshot(
        publication_session_factory,
        revision_id=old_active_id,
    )
    with publication_session_factory() as session:
        saved = save_product_candidate(
            session,
            product_id=product_id,
            expected_version=6,
            name="Legacy Null Candidate",
            description="candidate graph",
            actor_id=None,
        )
        candidate_id = saved.candidate_revision_id
    assert candidate_id is not None
    with publication_session_factory() as session:
        cloned = session.scalar(
            select(ProductRepositoryMapping).where(
                ProductRepositoryMapping.revision_id == candidate_id
            )
        )
        assert cloned is not None
        assert cloned.base_language is None

    before_rejected_publish = _graph_snapshot(
        publication_session_factory,
        product_id=product_id,
    )
    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationBlocked) as blocked,
    ):
        publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=7,
            actor_id=None,
        )
    assert tuple(blocker.value for blocker in blocked.value.blockers) == (
        "preview_confirmation_required",
    )
    assert (
        _graph_snapshot(
            publication_session_factory,
            product_id=product_id,
        )
        == before_rejected_publish
    )
    assert (
        _revision_graph_snapshot(
            publication_session_factory,
            revision_id=old_active_id,
        )
        == old_active_before
    )


def test_product_lock_linearizes_publish_equal_retry_and_stale_writer(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """Two sessions produce one pointer swap and one idempotent equal retry."""
    publication = _publication_module()
    product_id, old_active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory,
        is_active=False,
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
                actor_id=None,
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
        assert product.display_name == f"Candidate {product_id}"
        assert product.name_key == f"candidate {product_id}"
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
            actor_id=None,
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
            actor_id=None,
        )
    assert _graph_snapshot(publication_session_factory, product_id=product_id) == winner_snapshot


def test_normalized_name_conflict_rolls_back_identity_metadata_and_pointers(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """Publish-time A-01 uniqueness is bounded and leaves the full graph unchanged."""
    publication = _publication_module()
    product_id, _active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory
    )
    assert candidate_id is not None
    with publication_session_factory.begin() as session:
        session.add(
            Product(
                display_name=f"Ｃandidate {product_id}",
                name_key=f"candidate {product_id}",
                is_active=False,
            )
        )
    before = _graph_snapshot(publication_session_factory, product_id=product_id)

    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationConflict, match="identity conflict"),
    ):
        publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=7,
            confirmation_predicate=_always_confirmed,
            actor_id=None,
        )

    assert _graph_snapshot(publication_session_factory, product_id=product_id) == before


def test_noncanonical_candidate_identity_rolls_back_metadata_and_pointers(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """Publication rejects a durable candidate whose display/key pair is not canonical."""
    publication = _publication_module()
    product_id, _active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory
    )
    assert candidate_id is not None
    with publication_session_factory.begin() as session:
        candidate = session.get_one(ProductRevision, candidate_id)
        candidate.display_name = f"  Candidate {product_id}  "
    before = _graph_snapshot(publication_session_factory, product_id=product_id)

    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationConflict, match="identity conflict"),
    ):
        publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=7,
            confirmation_predicate=_always_confirmed,
            actor_id=None,
        )

    assert _graph_snapshot(publication_session_factory, product_id=product_id) == before


def test_unsupported_candidate_identity_is_bounded_and_rolls_back(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """Non-printable durable identity is projected as one bounded publication conflict."""
    publication = _publication_module()
    product_id, _active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory
    )
    assert candidate_id is not None
    with publication_session_factory.begin() as session:
        candidate = session.get_one(ProductRevision, candidate_id)
        candidate.display_name = "unsupported\x01identity"
    before = _graph_snapshot(publication_session_factory, product_id=product_id)

    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationConflict, match="identity conflict"),
    ):
        publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=7,
            confirmation_predicate=_always_confirmed,
            actor_id=None,
        )

    assert _graph_snapshot(publication_session_factory, product_id=product_id) == before


def test_publication_maps_commit_time_identity_integrity_race_to_conflict(
    publication_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A database uniqueness race remains bounded and rolls back the full graph."""
    publication = _publication_module()
    product_id, _active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory
    )
    assert candidate_id is not None
    before = _graph_snapshot(publication_session_factory, product_id=product_id)

    with publication_session_factory() as session:
        original_flush = session.flush
        flush_count = 0

        def inject_identity_race(*args: Any, **kwargs: Any) -> None:
            nonlocal flush_count
            flush_count += 1
            if flush_count == 2:
                raise IntegrityError("UPDATE products", {}, RuntimeError("unique race"))
            original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", inject_identity_race)
        with pytest.raises(publication.PublicationConflict, match="identity conflict"):
            publication.publish_product_candidate(
                session,
                product_id=product_id,
                candidate_revision_id=candidate_id,
                expected_candidate_version=7,
                confirmation_predicate=_always_confirmed,
                actor_id=None,
            )

    assert _graph_snapshot(publication_session_factory, product_id=product_id) == before


@pytest.mark.parametrize("failed_flush", (1, 2, 3))
def test_fault_at_publication_identity_or_pointer_flush_rolls_back_every_step(
    publication_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    failed_flush: int,
) -> None:
    """Failure after each promotion step preserves original identity and graph."""
    publication = _publication_module()
    product_id, _active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory
    )
    assert candidate_id is not None
    before = _graph_snapshot(publication_session_factory, product_id=product_id)

    with publication_session_factory() as session:
        original_flush = session.flush
        flush_count = 0

        def injected_flush(*args: Any, **kwargs: Any) -> None:
            nonlocal flush_count
            flush_count += 1
            original_flush(*args, **kwargs)
            if flush_count == failed_flush:
                raise RuntimeError(f"forced promotion failure {failed_flush}")

        monkeypatch.setattr(session, "flush", injected_flush)
        with pytest.raises(RuntimeError, match=f"forced promotion failure {failed_flush}"):
            publication.publish_product_candidate(
                session,
                product_id=product_id,
                candidate_revision_id=candidate_id,
                expected_candidate_version=7,
                confirmation_predicate=_always_confirmed,
                actor_id=None,
            )

    assert _graph_snapshot(publication_session_factory, product_id=product_id) == before


def test_new_active_mapping_children_remain_database_immutable_after_publication(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """Publication never bypasses Plan 24's active-child guards."""
    publication = _publication_module()
    product_id, _active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory
    )
    assert candidate_id is not None
    with publication_session_factory() as session:
        publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=7,
            confirmation_predicate=_always_confirmed,
            actor_id=None,
        )
    with publication_session_factory() as session:
        mapping_id = session.scalar(
            select(ProductRepositoryMapping.id).where(
                ProductRepositoryMapping.revision_id == candidate_id
            )
        )
    assert mapping_id is not None

    with (
        pytest.raises(Exception, match="active product revision graph is immutable"),
        publication_session_factory.begin() as session,
    ):
        session.execute(
            text(
                "UPDATE product_repository_mappings "
                "SET identity_key = identity_key || '-forbidden' WHERE id = :mapping_id"
            ),
            {"mapping_id": mapping_id},
        )
    with (
        pytest.raises(Exception, match="active product revision graph is immutable"),
        publication_session_factory.begin() as session,
    ):
        side = session.scalar(
            select(ProductMappingRepositorySide).where(
                ProductMappingRepositorySide.mapping_id == mapping_id
            )
        )
        assert side is not None
        side.source_branch = "forbidden"
        session.flush()


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
            actor_id=None,
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
        deactivated = publication.deactivate_product(session, product_id=product_id, actor_id=None)
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
            actor_id=None,
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
            actor_id=None,
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
            actor_id=None,
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


def test_current_confirmations_are_the_atomic_publication_and_reactivation_bridge(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """The real digest predicate permits one winner, equal retry, and reactivation."""
    publication = _publication_module()
    product_id, old_active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory
    )
    assert candidate_id is not None
    _confirm_revision_mappings(
        publication_session_factory,
        product_id=product_id,
        revision_id=candidate_id,
    )
    barrier = Barrier(2)

    def publish_once(_index: int) -> bool:
        with publication_session_factory() as session:
            barrier.wait()
            return publication.publish_product_candidate(
                session,
                product_id=product_id,
                candidate_revision_id=candidate_id,
                expected_candidate_version=7,
                actor_id=None,
            ).changed

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(publish_once, range(2)))

    assert sorted(results) == [False, True]
    with publication_session_factory() as session:
        product = session.get_one(Product, product_id)
        assert product.active_revision_id == candidate_id
        assert product.candidate_revision_id is None
        assert session.get_one(ProductRevision, old_active_id).is_published is True

    with publication_session_factory() as session:
        publication.deactivate_product(session, product_id=product_id, actor_id=None)
    with publication_session_factory() as session:
        reactivated = publication.reactivate_product(
            session,
            product_id=product_id,
            active_revision_id=candidate_id,
            expected_active_version=7,
            actor_id=None,
        )
    assert reactivated.changed is True
    assert reactivated.is_active is True


def test_every_mapping_requires_one_current_exact_confirmation(
    publication_session_factory: sessionmaker[Session],
) -> None:
    """One confirmed mapping cannot authorize an otherwise valid multi-mapping graph."""
    publication = _publication_module()
    product_id, _active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory,
        candidate_mapping_count=2,
    )
    assert candidate_id is not None
    with publication_session_factory() as session:
        mapping_ids = tuple(
            session.scalars(
                select(ProductRepositoryMapping.id)
                .where(ProductRepositoryMapping.revision_id == candidate_id)
                .order_by(ProductRepositoryMapping.id)
            )
        )
    assert len(mapping_ids) == 2
    _confirm_revision_mappings(
        publication_session_factory,
        product_id=product_id,
        revision_id=candidate_id,
        mapping_ids={mapping_ids[0]},
    )
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
            actor_id=None,
        )

    assert tuple(blocker.value for blocker in blocked.value.blockers) == (
        "preview_confirmation_required",
    )
    assert _graph_snapshot(publication_session_factory, product_id=product_id) == before

    _confirm_revision_mappings(
        publication_session_factory,
        product_id=product_id,
        revision_id=candidate_id,
        mapping_ids={mapping_ids[1]},
    )
    with publication_session_factory() as session:
        published = publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=7,
            actor_id=None,
        )
    assert published.changed is True
    assert published.active_revision_id == candidate_id


@pytest.mark.parametrize(
    "mutation",
    (
        "candidate_version",
        "connection_generation",
        "branch",
        "new_commit",
        "job_failed",
        "result",
        "digest",
        "layout",
        "detector_version",
        "layout_identity",
    ),
)
def test_stale_confirmation_identity_preserves_the_prior_active_graph(
    publication_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    """Every stale candidate/job/generation/commit/layout identity fails atomically."""
    publication = _publication_module()
    preview_jobs = importlib.import_module("verboflex.services.preview_jobs")
    product_id, old_active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory
    )
    assert candidate_id is not None
    (confirmed_job_id,) = _confirm_revision_mappings(
        publication_session_factory,
        product_id=product_id,
        revision_id=candidate_id,
    )
    expected_version = 7

    if mutation in {"detector_version", "layout_identity"}:
        constant = (
            "PREVIEW_DETECTOR_VERSION"
            if mutation == "detector_version"
            else "PREVIEW_LAYOUT_IDENTITY"
        )
        monkeypatch.setattr(preview_jobs, constant, f"changed-{mutation}-v2")
    elif mutation == "new_commit":
        with publication_session_factory() as session:
            mapping_id = session.scalar(
                select(ProductRepositoryMapping.id).where(
                    ProductRepositoryMapping.revision_id == candidate_id
                )
            )
        assert mapping_id is not None
        with publication_session_factory() as session:
            newer = create_or_reuse_preview_job(
                session,
                product_id=product_id,
                mapping_id=mapping_id,
                expected_candidate_version=7,
                commits={"direct": "b" * 40},
                enqueuer=lambda _job_id: None,
                actor_id=None,
            )
        with publication_session_factory.begin() as session:
            row = session.get_one(PreviewJob, newer.id)
            row.created_at = datetime.now(UTC) + timedelta(minutes=1)
    else:
        with publication_session_factory.begin() as session:
            mapping = session.scalar(
                select(ProductRepositoryMapping).where(
                    ProductRepositoryMapping.revision_id == candidate_id
                )
            )
            assert mapping is not None
            if mutation == "candidate_version":
                revision = session.get_one(ProductRevision, candidate_id)
                revision.version += 1
                expected_version = 8
            elif mutation == "connection_generation":
                session.get_one(BitbucketConnection, 1).generation += 1
            elif mutation == "branch":
                side = session.scalar(
                    select(ProductMappingRepositorySide).where(
                        ProductMappingRepositorySide.mapping_id == mapping.id
                    )
                )
                assert side is not None
                side.source_branch = "release/drift"
            elif mutation == "job_failed":
                session.execute(
                    text(
                        "UPDATE preview_jobs SET state = 'failed', result = NULL, "
                        "error_code = 'processing_failed' WHERE id = :job_id"
                    ),
                    {"job_id": confirmed_job_id},
                )
            elif mutation == "digest":
                mapping.confirmed_preview_digest = "f" * 64
            elif mutation == "result":
                job = session.get_one(PreviewJob, confirmed_job_id)
                job.result = {
                    "detector_version": PREVIEW_DETECTOR_VERSION,
                    "digest": job.input_digest,
                    "layout_candidates": [{}],
                }
            else:
                mapping.selected_layout_candidate_id = uuid4()

    before = _graph_snapshot(publication_session_factory, product_id=product_id)
    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationBlocked) as blocked,
    ):
        publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=expected_version,
            actor_id=None,
        )

    assert tuple(blocker.value for blocker in blocked.value.blockers) == (
        "preview_confirmation_required",
    )
    after = _graph_snapshot(publication_session_factory, product_id=product_id)
    assert after == before
    assert after[0][2] == old_active_id


def _active_revalidation_processor(mapping_id: UUID) -> Any:
    candidate = _preview_candidate(mapping_id)

    def processor(identity: Any) -> dict[str, object]:
        return {
            "detector_version": identity.detector_version,
            "digest": identity.input_digest,
            "layout_candidates": [candidate],
        }

    return processor


@pytest.mark.parametrize("authority_drift", ("generation", "commit", "version", "mapping"))
def test_generation_commit_version_and_mapping_drift_block_reactivation_until_reconfirmed(
    publication_session_factory: sessionmaker[Session],
    authority_drift: str,
) -> None:
    """Every stale sidecar tuple fails closed until a new exact job is confirmed."""
    publication = _publication_module()
    product_id, _old_active_id, candidate_id, _repository_id = _seed_product_graph(
        publication_session_factory,
        candidate_mapping_count=2,
    )
    assert candidate_id is not None
    _confirm_revision_mappings(
        publication_session_factory,
        product_id=product_id,
        revision_id=candidate_id,
    )
    with publication_session_factory() as session:
        publication.publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=candidate_id,
            expected_candidate_version=7,
            actor_id=None,
        )
    with publication_session_factory() as session:
        publication.deactivate_product(session, product_id=product_id, actor_id=None)
    actor_id = uuid4()
    with publication_session_factory.begin() as session:
        session.add(
            User(
                id=actor_id,
                email=f"active-revalidation-{actor_id}@example.com",
                display_name="Active Revalidation Admin",
                hashed_password=hash_password("active revalidation administrator phrase!"),
                is_active=True,
                must_change_password=False,
            )
        )
        session.get_one(BitbucketConnection, 1).generation += 1
    with publication_session_factory() as session:
        mapping_ids = tuple(
            session.scalars(
                select(ProductRepositoryMapping.id)
                .where(ProductRepositoryMapping.revision_id == candidate_id)
                .order_by(ProductRepositoryMapping.id)
            )
        )
    assert len(mapping_ids) == 2
    mapping_id = mapping_ids[0]
    original_jobs = []
    for initial_mapping_id in mapping_ids:
        with publication_session_factory() as session:
            initial = create_or_reuse_active_revision_revalidation_job(
                session,
                product_id=product_id,
                active_revision_id=candidate_id,
                mapping_id=initial_mapping_id,
                expected_active_revision_version=7,
                commits={"direct": "a" * 40},
                enqueuer=lambda _job_id: None,
                actor_id=None,
            )
        execute_preview_job(
            publication_session_factory,
            job_id=initial.id,
            processor=_active_revalidation_processor(initial_mapping_id),
        )
        with publication_session_factory() as session:
            initial_result = get_active_revision_revalidation_job(
                session,
                job_id=initial.id,
            )
            assert initial_result.result is not None
            initial_selected = initial_result.result["layout_candidates"][0]
        assert isinstance(initial_selected, dict)
        with publication_session_factory() as session:
            confirm_active_revision_revalidation(
                session,
                job_id=initial.id,
                preview_digest=str(initial_result.result["digest"]),
                layout_candidate_id=UUID(str(initial_selected["id"])),
                layout_candidate_version=1,
                actor_id=actor_id,
            )
        original_jobs.append(initial)
    original = original_jobs[0]

    replacement = None
    if authority_drift == "generation":
        with publication_session_factory.begin() as session:
            session.get_one(BitbucketConnection, 1).generation += 1
    elif authority_drift == "commit":
        with publication_session_factory() as session:
            replacement = create_or_reuse_active_revision_revalidation_job(
                session,
                product_id=product_id,
                active_revision_id=candidate_id,
                mapping_id=mapping_id,
                expected_active_revision_version=7,
                commits={"direct": "b" * 40},
                enqueuer=lambda _job_id: None,
                actor_id=None,
            )
    else:
        with publication_session_factory.begin() as session:
            if authority_drift == "version":
                session.execute(
                    text(
                        "UPDATE preview_jobs SET state = 'failed', result = NULL, "
                        "error_code = 'processing_failed', "
                        "candidate_revision_version = candidate_revision_version + 1 "
                        "WHERE id = :job_id"
                    ),
                    {"job_id": original.id},
                )
            else:
                session.execute(
                    text(
                        "UPDATE preview_jobs SET state = 'failed', result = NULL, "
                        "error_code = 'processing_failed', mapping_id = :mapping_id "
                        "WHERE id = :job_id"
                    ),
                    {"job_id": original.id, "mapping_id": mapping_ids[1]},
                )

    blocked_snapshot = _graph_snapshot(publication_session_factory, product_id=product_id)
    with (
        publication_session_factory() as session,
        pytest.raises(publication.PublicationBlocked) as blocked,
    ):
        publication.reactivate_product(
            session,
            product_id=product_id,
            active_revision_id=candidate_id,
            expected_active_version=7,
            actor_id=None,
        )
    assert tuple(blocker.value for blocker in blocked.value.blockers) == (
        "preview_confirmation_required",
    )
    assert _graph_snapshot(publication_session_factory, product_id=product_id) == blocked_snapshot

    if replacement is None:
        with publication_session_factory() as session:
            replacement = create_or_reuse_active_revision_revalidation_job(
                session,
                product_id=product_id,
                active_revision_id=candidate_id,
                mapping_id=mapping_id,
                expected_active_revision_version=7,
                commits={"direct": "a" * 40},
                enqueuer=lambda _job_id: None,
                actor_id=None,
            )
    execute_preview_job(
        publication_session_factory,
        job_id=replacement.id,
        processor=_active_revalidation_processor(mapping_id),
    )
    with publication_session_factory() as session:
        current = get_active_revision_revalidation_job(session, job_id=replacement.id)
        assert current.result is not None
        current_selected = current.result["layout_candidates"][0]
    assert isinstance(current_selected, dict)
    confirmation_barrier = Barrier(2)

    def confirm_once(_index: int) -> UUID:
        with publication_session_factory() as session:
            confirmation_barrier.wait()
            return confirm_active_revision_revalidation(
                session,
                job_id=replacement.id,
                preview_digest=str(current.result["digest"]),
                layout_candidate_id=UUID(str(current_selected["id"])),
                layout_candidate_version=1,
                actor_id=actor_id,
            ).job_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        confirmation_jobs = tuple(executor.map(confirm_once, range(2)))
    assert confirmation_jobs == (replacement.id, replacement.id)

    if authority_drift == "generation":
        secondary_mapping_id = mapping_ids[1]
        with publication_session_factory() as session:
            secondary = create_or_reuse_active_revision_revalidation_job(
                session,
                product_id=product_id,
                active_revision_id=candidate_id,
                mapping_id=secondary_mapping_id,
                expected_active_revision_version=7,
                commits={"direct": "a" * 40},
                enqueuer=lambda _job_id: None,
                actor_id=None,
            )
        execute_preview_job(
            publication_session_factory,
            job_id=secondary.id,
            processor=_active_revalidation_processor(secondary_mapping_id),
        )
        with publication_session_factory() as session:
            secondary_result = get_active_revision_revalidation_job(
                session,
                job_id=secondary.id,
            )
            assert secondary_result.result is not None
            secondary_selected = secondary_result.result["layout_candidates"][0]
        assert isinstance(secondary_selected, dict)
        with publication_session_factory() as session:
            confirm_active_revision_revalidation(
                session,
                job_id=secondary.id,
                preview_digest=str(secondary_result.result["digest"]),
                layout_candidate_id=UUID(str(secondary_selected["id"])),
                layout_candidate_version=1,
                actor_id=actor_id,
            )

    reactivation_barrier = Barrier(2)

    def reactivate_once(_index: int) -> bool:
        with publication_session_factory() as session:
            reactivation_barrier.wait()
            return publication.reactivate_product(
                session,
                product_id=product_id,
                active_revision_id=candidate_id,
                expected_active_version=7,
                actor_id=None,
            ).changed

    with ThreadPoolExecutor(max_workers=2) as executor:
        reactivation_results = tuple(executor.map(reactivate_once, range(2)))
    assert sorted(reactivation_results) == [False, True]
    after = _graph_snapshot(publication_session_factory, product_id=product_id)
    assert after[0][1] is True
    assert after[0][2:] == blocked_snapshot[0][2:]
    assert after[1:] == blocked_snapshot[1:]
