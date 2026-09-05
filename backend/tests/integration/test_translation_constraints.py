"""Transactional maximum-length inheritance and mutation contracts."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_mapping
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.translation import LocalizationScope, TranslationKey, TranslationValue
from verboflex.models.translation_constraint import TranslationConstraint
from verboflex.models.user import User
from verboflex.services import import_jobs
from verboflex.services.bitbucket_oauth import PULLREQUEST_WRITE_SCOPE
from verboflex.services.import_jobs import ImportSourceReferenceRecord

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)


@pytest.fixture(scope="module")
def constraint_session_factory() -> Iterator[sessionmaker[Session]]:
    database_name = f"verboflex_translation_constraints_{uuid4().hex}"
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
def clean_constraint_database(
    constraint_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    with constraint_session_factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories CASCADE"))
        connection = session.get_one(BitbucketConnection, 1)
        connection.generation = 9
        connection.access_token_ciphertext = "encrypted-access"
        connection.refresh_token_ciphertext = None
        connection.scope_profile = PULLREQUEST_WRITE_SCOPE
        connection.provider_expires_at = datetime.now(UTC) + timedelta(hours=1)
        connection.connected_at = datetime.now(UTC)
        connection.revoked_at = None
    yield


def _translation_constraints() -> Any:
    assert importlib.util.find_spec("verboflex.services.translation_constraints") is not None
    return importlib.import_module("verboflex.services.translation_constraints")


def _translation_imports() -> Any:
    return importlib.import_module("verboflex.services.translation_imports")


def _selector_digest(selector_bytes: bytes) -> str:
    return hashlib.sha256(selector_bytes).hexdigest()


def _seed_constraint_dataset(
    factory: sessionmaker[Session],
    *,
    base_language: str | None = "en",
    target_text: str = "Ciao",
) -> dict[str, UUID]:
    ids = {
        "actor": uuid4(),
        "base_key": uuid4(),
        "base_repository": uuid4(),
        "base_value": uuid4(),
        "mapping": uuid4(),
        "product": uuid4(),
        "revision": uuid4(),
        "scope": uuid4(),
        "target_key": uuid4(),
        "target_repository": uuid4(),
        "target_value": uuid4(),
    }
    base_selector = b'{"kind":"scalar","schema_version":1}'
    target_selector = b'{"kind":"scalar","schema_version":1}'
    with factory.begin() as session:
        product = Product(
            id=ids["product"],
            display_name=f"Constraint product {ids['product']}",
            name_key=f"constraint product {ids['product']}",
            is_active=True,
        )
        session.add(product)
        session.flush()
        session.add_all(
            [
                ProductRevision(
                    id=ids["revision"],
                    product_id=ids["product"],
                    description="published constraints",
                    version=1,
                    is_published=False,
                ),
                Repository(
                    id=ids["base_repository"],
                    workspace="constraint-team",
                    repository_slug=f"keys-{ids['base_repository'].hex}",
                    descriptive_name="Constraint keys",
                    descriptive_name_key="constraint keys",
                ),
                Repository(
                    id=ids["target_repository"],
                    workspace="constraint-team",
                    repository_slug=f"translations-{ids['target_repository'].hex}",
                    descriptive_name="Constraint translations",
                    descriptive_name_key="constraint translations",
                ),
                User(
                    id=ids["actor"],
                    email=f"constraint-{ids['actor']}@example.com",
                    display_name="Constraint reviewer",
                    hashed_password="not-used-by-constraint-tests",
                    is_active=True,
                    must_change_password=False,
                ),
            ]
        )
        session.flush()
        mapping = ProductRepositoryMapping(
            id=ids["mapping"],
            revision_id=ids["revision"],
            topology="separate",
            identity_key=(
                f'[["keys","{ids["base_repository"]}","main"],'
                f'["translations","{ids["target_repository"]}","main"]]'
            ),
            base_language=base_language,
            sides=[
                ProductMappingRepositorySide(
                    role="keys",
                    repository_id=ids["base_repository"],
                    source_branch="main",
                ),
                ProductMappingRepositorySide(
                    role="translations",
                    repository_id=ids["target_repository"],
                    source_branch="main",
                ),
            ],
            allowed_targets=[ProductMappingAllowedTarget(branch="main", is_default=True)],
        )
        session.add(mapping)
        session.flush()
        revision = session.get_one(ProductRevision, ids["revision"])
        revision.is_published = True
        revision.published_at = datetime.now(UTC)
        session.flush()
        product.active_revision_id = ids["revision"]
        session.flush()
        scope = LocalizationScope(
            id=ids["scope"],
            product_id=ids["product"],
            mapping_identity_key=mapping.identity_key,
            current_revision_id=ids["revision"],
            current_mapping_id=ids["mapping"],
        )
        session.add(scope)
        session.flush()
        session.add_all(
            [
                TranslationKey(
                    id=ids["base_key"],
                    scope_id=ids["scope"],
                    product_id=ids["product"],
                    repository_id=ids["base_repository"],
                    configured_branch="main",
                    raw_key="welcome",
                ),
                TranslationKey(
                    id=ids["target_key"],
                    scope_id=ids["scope"],
                    product_id=ids["product"],
                    repository_id=ids["target_repository"],
                    configured_branch="main",
                    raw_key="welcome",
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                TranslationValue(
                    id=ids["base_value"],
                    scope_id=ids["scope"],
                    translation_key_id=ids["base_key"],
                    language="en",
                    selector_version=1,
                    selector_kind="scalar",
                    selector_bytes=base_selector,
                    selector_digest=_selector_digest(base_selector),
                    source_text="Hello",
                    translated_text="Hello",
                    display_text="Hello",
                    structure=[],
                    review_state="draft",
                ),
                TranslationValue(
                    id=ids["target_value"],
                    scope_id=ids["scope"],
                    translation_key_id=ids["target_key"],
                    language="it",
                    selector_version=1,
                    selector_kind="scalar",
                    selector_bytes=target_selector,
                    selector_digest=_selector_digest(target_selector),
                    source_text=None,
                    translated_text=target_text,
                    display_text=target_text,
                    structure=[],
                    review_state="draft",
                ),
            ]
        )
    return ids


def _explicit_constraint(
    *,
    ids: dict[str, UUID],
    key: str,
    language: str,
    maximum: int,
) -> TranslationConstraint:
    return TranslationConstraint(
        scope_id=ids["scope"],
        translation_key_id=ids[key],
        language=language,
        max_chars=maximum,
        created_by=ids["actor"],
        updated_by=ids["actor"],
    )


def test_inheritance_projection_labels_default_inherited_override_and_none() -> None:
    service = _translation_constraints()
    base_default = TranslationConstraint(language="en", max_chars=5)
    override = TranslationConstraint(language="it", max_chars=3)

    default = service.project_effective_constraint(
        language="en",
        base_language="en",
        explicit_constraint=base_default,
        base_constraint=base_default,
    )
    inherited = service.project_effective_constraint(
        language="it",
        base_language="en",
        explicit_constraint=None,
        base_constraint=base_default,
    )
    overridden = service.project_effective_constraint(
        language="it",
        base_language="en",
        explicit_constraint=override,
        base_constraint=base_default,
    )
    absent = service.project_effective_constraint(
        language="it",
        base_language="en",
        explicit_constraint=None,
        base_constraint=None,
    )

    assert (default.maximum, default.source, default.label) == (5, "base_default", "default")
    assert (inherited.maximum, inherited.source, inherited.label) == (
        5,
        "base_default",
        "inherited",
    )
    assert (overridden.maximum, overridden.source, overridden.label) == (
        3,
        "language_override",
        "override",
    )
    assert (absent.maximum, absent.source, absent.label) == (None, "none", "none")


def test_recompute_fans_dynamic_base_default_across_repository_keys(
    constraint_session_factory: sessionmaker[Session],
) -> None:
    service = _translation_constraints()
    ids = _seed_constraint_dataset(constraint_session_factory)
    with constraint_session_factory.begin() as session:
        base_default = _explicit_constraint(
            ids=ids,
            key="base_key",
            language="en",
            maximum=4,
        )
        session.add(base_default)
        service.recompute_translation_constraints(
            session,
            scope_id=ids["scope"],
        )
        target = session.get_one(TranslationValue, ids["target_value"])
        assert (target.effective_max_chars, target.effective_constraint_source) == (
            4,
            "base_default",
        )
        assert target.is_over_limit is False

        base_default.max_chars = 3
        base_default.version += 1
        service.recompute_translation_constraints(
            session,
            scope_id=ids["scope"],
            raw_key="welcome",
        )
        assert target.effective_max_chars == 3
        assert target.is_over_limit is True


def test_recompute_preserves_independent_target_override_on_base_change(
    constraint_session_factory: sessionmaker[Session],
) -> None:
    service = _translation_constraints()
    ids = _seed_constraint_dataset(constraint_session_factory)
    with constraint_session_factory.begin() as session:
        base_default = _explicit_constraint(
            ids=ids,
            key="base_key",
            language="en",
            maximum=2,
        )
        override = _explicit_constraint(
            ids=ids,
            key="target_key",
            language="it",
            maximum=10,
        )
        session.add_all([base_default, override])
        service.recompute_translation_constraints(session, scope_id=ids["scope"])
        base_default.max_chars = 1
        base_default.version += 1
        service.recompute_translation_constraints(session, scope_id=ids["scope"])
        target = session.get_one(TranslationValue, ids["target_value"])

    assert (target.effective_max_chars, target.effective_constraint_source) == (
        10,
        "language_override",
    )
    assert target.is_over_limit is False


def test_grapheme_recompute_counts_visible_text_without_normalizing_it(
    constraint_session_factory: sessionmaker[Session],
) -> None:
    service = _translation_constraints()
    visible_text = "e\u0301👨‍👩‍👧‍👦"
    ids = _seed_constraint_dataset(
        constraint_session_factory,
        target_text=visible_text,
    )
    with constraint_session_factory.begin() as session:
        session.add(
            _explicit_constraint(
                ids=ids,
                key="base_key",
                language="en",
                maximum=1,
            )
        )
        projections = service.recompute_translation_constraints(
            session,
            scope_id=ids["scope"],
        )
        target = session.get_one(TranslationValue, ids["target_value"])
        target_projection = next(item for item in projections if item.value_id == target.id)

    assert target.display_text == visible_text
    assert target.grapheme_count == 2
    assert target.is_over_limit is True
    assert target.review_state == "draft"
    assert target_projection.approval_eligible is False
    assert target_projection.submission_eligible is False


def test_recompute_empty_scope_is_a_valid_noop_and_missing_base_is_rejected(
    constraint_session_factory: sessionmaker[Session],
) -> None:
    service = _translation_constraints()
    ids = _seed_constraint_dataset(constraint_session_factory)
    with constraint_session_factory.begin() as session:
        session.execute(
            text("DELETE FROM translation_values WHERE scope_id = :scope_id"),
            {"scope_id": ids["scope"]},
        )
        assert (
            service.recompute_translation_constraints(
                session,
                scope_id=ids["scope"],
            )
            == ()
        )
        mapping = session.get_one(ProductRepositoryMapping, ids["mapping"])
        mapping.base_language = None
        session.flush()
        with pytest.raises(service.ConstraintAuthorityUnavailable):
            service.recompute_translation_constraints(
                session,
                scope_id=ids["scope"],
            )


def test_recompute_tombstone_retains_exact_authoritative_projection(
    constraint_session_factory: sessionmaker[Session],
) -> None:
    service = _translation_constraints()
    ids = _seed_constraint_dataset(constraint_session_factory, target_text="Ciao")
    with constraint_session_factory.begin() as session:
        session.add(
            _explicit_constraint(
                ids=ids,
                key="base_key",
                language="en",
                maximum=3,
            )
        )
        target = session.get_one(TranslationValue, ids["target_value"])
        target.is_deleted = True
        target.deleted_at = datetime.now(UTC)
        projections = service.recompute_translation_constraints(
            session,
            scope_id=ids["scope"],
        )
        target_projection = next(item for item in projections if item.value_id == target.id)

    assert (target.grapheme_count, target.effective_max_chars, target.is_over_limit) == (
        4,
        3,
        True,
    )
    assert target_projection.approval_eligible is False
    assert target_projection.submission_eligible is False


def test_recompute_after_translation_edit_uses_the_same_grapheme_authority(
    constraint_session_factory: sessionmaker[Session],
) -> None:
    service = _translation_constraints()
    ids = _seed_constraint_dataset(constraint_session_factory)
    edited_text = "👩🏽‍💻e\u0301"
    with constraint_session_factory.begin() as session:
        session.add(
            _explicit_constraint(
                ids=ids,
                key="base_key",
                language="en",
                maximum=1,
            )
        )
        target = session.get_one(TranslationValue, ids["target_value"])
        target.display_text = edited_text
        target.translated_text = edited_text
        projection = service.recompute_after_translation_edit(session, value=target)

    assert target.display_text == edited_text
    assert (projection.actual, projection.maximum, projection.source) == (
        2,
        1,
        "base_default",
    )
    assert projection.is_over_limit is True


def _seed_running_direct_import(
    factory: sessionmaker[Session],
) -> tuple[import_jobs.ImportExecutionIdentity, UUID]:
    product_id = uuid4()
    revision_id = uuid4()
    repository_id = uuid4()
    mapping_id = uuid4()
    now = datetime.now(UTC)
    with factory.begin() as session:
        product = Product(
            id=product_id,
            display_name=f"Constraint import {product_id}",
            name_key=f"constraint import {product_id}",
            is_active=True,
        )
        session.add(product)
        session.flush()
        session.add_all(
            [
                ProductRevision(
                    id=revision_id,
                    product_id=product_id,
                    description="published constraint import",
                    version=1,
                    is_published=False,
                ),
                Repository(
                    id=repository_id,
                    workspace="constraint-team",
                    repository_slug=f"constraint-{repository_id.hex}",
                    descriptive_name="Constraint import source",
                    descriptive_name_key="constraint import source",
                ),
            ]
        )
        session.flush()
        session.add(
            ProductRepositoryMapping(
                id=mapping_id,
                revision_id=revision_id,
                topology="direct",
                identity_key=f'[["direct","{repository_id}","main"]]',
                base_language="en",
                sides=[
                    ProductMappingRepositorySide(
                        role="direct",
                        repository_id=repository_id,
                        source_branch="main",
                    )
                ],
                allowed_targets=[ProductMappingAllowedTarget(branch="main", is_default=True)],
            )
        )
        session.flush()
        revision = session.get_one(ProductRevision, revision_id)
        revision.is_published = True
        revision.published_at = now
        session.flush()
        product.active_revision_id = revision_id
    with factory() as session:
        record = import_jobs.start_or_refresh_import(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            enqueuer=lambda _import_id: None,
        )
    assert record.id is not None
    identity = import_jobs.start_import_execution(factory, import_id=record.id)
    assert identity is not None
    return identity, repository_id


def _activate_json_import(
    factory: sessionmaker[Session],
    *,
    identity: import_jobs.ImportExecutionIdentity,
    repository_id: UUID,
    translated: str,
    commit_hash: str,
) -> None:
    result = parse_canonical_mapping(
        (
            CanonicalParserInput(
                format="json",
                repository_side="direct",
                path="locales.json",
                content=(
                    '{"en":{"welcome":"Hello"},"it":{"welcome":"' + translated + '"}}'
                ).encode(),
                layout_identity="json:locale-rooted:locales.json",
                layout_version=1,
                base_language="en",
            ),
        )
    )
    references = (
        ImportSourceReferenceRecord(
            position=0,
            repository_side="direct",
            repository_id=repository_id,
            source_branch="main",
            commit_hash=commit_hash,
            path="locales.json",
            size_bytes=64,
            sha256="b" * 64,
        ),
    )
    manifest = _translation_imports().stage_translation_parse(
        factory,
        identity=identity,
        references=references,
        result=result,
    )
    assert manifest is not None
    assert import_jobs.finish_import_execution(
        factory,
        identity=identity,
        references=references,
        canonical_manifest_digest=manifest.digest,
    )


def test_import_activation_recomputes_violation_and_eligibility_in_one_transaction(
    constraint_session_factory: sessionmaker[Session],
) -> None:
    identity, repository_id = _seed_running_direct_import(constraint_session_factory)
    _activate_json_import(
        constraint_session_factory,
        identity=identity,
        repository_id=repository_id,
        translated="Ciao",
        commit_hash="a" * 40,
    )
    with constraint_session_factory.begin() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
        assert scope is not None
        base_key = session.execute(
            select(TranslationKey)
            .join(TranslationValue)
            .where(
                TranslationKey.scope_id == scope.id,
                TranslationKey.raw_key == "welcome",
                TranslationValue.language == "en",
            )
        ).scalar_one()
        actor_id = uuid4()
        session.add(
            User(
                id=actor_id,
                email=f"import-constraint-{actor_id}@example.com",
                display_name="Import constraint reviewer",
                hashed_password="not-used-by-constraint-tests",
                is_active=True,
                must_change_password=False,
            )
        )
        session.add(
            TranslationConstraint(
                scope_id=scope.id,
                translation_key_id=base_key.id,
                language="en",
                max_chars=3,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
    with constraint_session_factory.begin() as session:
        execution = session.get_one(
            import_jobs.ImportExecution,
            identity.execution_id,
        )
        job = session.get_one(import_jobs.ImportJob, identity.import_id)
        execution.state = "succeeded"
        execution.finished_at = execution.finished_at or datetime.now(UTC)
        job.state = "current"
        job.active_baseline_execution_id = execution.id
    with constraint_session_factory() as session:
        import_jobs.start_or_refresh_import(
            session,
            product_id=identity.product_id,
            mapping_id=identity.mapping_id,
            enqueuer=lambda _import_id: None,
        )
    successor = import_jobs.start_import_execution(
        constraint_session_factory,
        import_id=identity.import_id,
    )
    assert successor is not None
    _activate_json_import(
        constraint_session_factory,
        identity=successor,
        repository_id=repository_id,
        translated="👩🏽‍💻Ciao",
        commit_hash="c" * 40,
    )

    with constraint_session_factory() as session:
        target = session.execute(
            select(TranslationValue)
            .join(TranslationKey)
            .where(
                TranslationKey.scope_id
                == select(LocalizationScope.id)
                .where(LocalizationScope.product_id == identity.product_id)
                .scalar_subquery(),
                TranslationKey.raw_key == "welcome",
                TranslationValue.language == "it",
            )
        ).scalar_one()
    assert target.display_text == "👩🏽‍💻Ciao"
    assert target.grapheme_count == 5
    assert target.effective_max_chars == 3
    assert target.effective_constraint_source == "base_default"
    assert target.is_over_limit is True
    assert target.review_state == "draft"
