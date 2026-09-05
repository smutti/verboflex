"""Canonical import staging, reconciliation, and atomic activation contracts."""

from __future__ import annotations

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
from verboflex.localization.importing.core import (
    CanonicalIssue,
    CanonicalParseResult,
    CanonicalParserInput,
    canonical_selector_bytes,
)
from verboflex.localization.importing.registry import parse_canonical_mapping
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.import_job import ImportExecution, ImportJob, ImportSourceReference
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.translation import (
    LocalizationScope,
    StagedTranslationValue,
    TranslationKey,
    TranslationParseIssue,
    TranslationValue,
    TranslationValueLocator,
    TranslationValueRevision,
)
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
def activation_session_factory() -> Iterator[sessionmaker[Session]]:
    database_name = f"verboflex_translation_activation_{uuid4().hex}"
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
def clean_activation_database(
    activation_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    with activation_session_factory.begin() as session:
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


def _translation_imports() -> Any:
    assert importlib.util.find_spec("verboflex.services.translation_imports") is not None
    return importlib.import_module("verboflex.services.translation_imports")


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
            display_name=f"Canonical import {product_id}",
            name_key=f"canonical import {product_id}",
            is_active=True,
        )
        session.add(product)
        session.flush()
        session.add_all(
            [
                ProductRevision(
                    id=revision_id,
                    product_id=product_id,
                    description="published canonical import",
                    version=1,
                    is_published=False,
                ),
                Repository(
                    id=repository_id,
                    workspace="canonical-team",
                    repository_slug=f"canonical-{repository_id.hex}",
                    descriptive_name="Canonical source",
                    descriptive_name_key="canonical source",
                ),
            ]
        )
        session.flush()
        session.add(
            ProductRepositoryMapping(
                id=mapping_id,
                revision_id=revision_id,
                topology="direct",
                identity_key=f'["direct","{repository_id}","main"]',
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

    record = import_jobs.start_or_refresh_import(
        factory(),
        product_id=product_id,
        mapping_id=mapping_id,
        enqueuer=lambda _import_id: None,
    )
    assert record.id is not None
    identity = import_jobs.start_import_execution(factory, import_id=record.id)
    assert identity is not None
    return identity, repository_id


def _reference(
    repository_id: UUID,
    *,
    commit_hash: str = "a" * 40,
    path: str = "locales.json",
) -> ImportSourceReferenceRecord:
    return ImportSourceReferenceRecord(
        position=0,
        repository_side="direct",
        repository_id=repository_id,
        source_branch="main",
        commit_hash=commit_hash,
        path=path,
        size_bytes=48,
        sha256="b" * 64,
    )


def _direct_result(*, path: str = "locales.json") -> CanonicalParseResult:
    return parse_canonical_mapping(
        (
            CanonicalParserInput(
                format="json",
                repository_side="direct",
                path=path,
                content=b'{"en":{"welcome":"Hello"},"it":{"welcome":"Ciao"}}',
                layout_identity=f"json:locale-rooted:{path}",
                layout_version=1,
                base_language="en",
            ),
        )
    )


def _json_result(
    *,
    source: str = "Hello",
    translated: str = "Ciao",
    raw_key: str = "welcome",
    path: str = "locales.json",
) -> CanonicalParseResult:
    content = (
        '{"en":{"' + raw_key + '":"' + source + '"},"it":{"' + raw_key + '":"' + translated + '"}}'
    ).encode()
    return parse_canonical_mapping(
        (
            CanonicalParserInput(
                format="json",
                repository_side="direct",
                path=path,
                content=content,
                layout_identity=f"json:locale-rooted:{path}",
                layout_version=1,
                base_language="en",
            ),
        )
    )


def _reconcile_staged_result(
    factory: sessionmaker[Session],
    *,
    identity: import_jobs.ImportExecutionIdentity,
    repository_id: UUID,
    result: CanonicalParseResult,
    path: str = "locales.json",
    commit_hash: str = "a" * 40,
    correlations: dict[tuple[UUID, str, str, bytes], str] | None = None,
) -> Any:
    translation_imports = _translation_imports()
    manifest = translation_imports.stage_translation_parse(
        factory,
        identity=identity,
        references=(_reference(repository_id, commit_hash=commit_hash, path=path),),
        result=result,
        correlation_references=correlations,
    )
    assert manifest is not None and manifest.complete
    with factory.begin() as session:
        scope = session.scalar(
            select(LocalizationScope)
            .where(LocalizationScope.product_id == identity.product_id)
            .with_for_update()
        )
        assert scope is not None
        return translation_imports.reconcile_canonical_translations(
            session,
            identity=identity,
            scope=scope,
            manifest_digest=manifest.digest,
        )


def _start_refresh_execution(
    factory: sessionmaker[Session],
    identity: import_jobs.ImportExecutionIdentity,
) -> import_jobs.ImportExecutionIdentity:
    with factory.begin() as session:
        execution = session.get_one(ImportExecution, identity.execution_id)
        job = session.get_one(ImportJob, identity.import_id)
        execution.state = "succeeded"
        execution.finished_at = datetime.now(UTC)
        job.state = "current"
        job.active_baseline_execution_id = execution.id
    with factory() as session:
        refreshed = import_jobs.start_or_refresh_import(
            session,
            product_id=identity.product_id,
            mapping_id=identity.mapping_id,
            enqueuer=lambda _import_id: None,
        )
    assert refreshed.id == identity.import_id
    successor = import_jobs.start_import_execution(factory, import_id=identity.import_id)
    assert successor is not None
    return successor


def _value_for(
    session: Session,
    *,
    scope_id: UUID,
    raw_key: str,
    language: str,
) -> TranslationValue:
    return session.execute(
        select(TranslationValue)
        .join(TranslationKey, TranslationKey.id == TranslationValue.translation_key_id)
        .where(
            TranslationKey.scope_id == scope_id,
            TranslationKey.raw_key == raw_key,
            TranslationValue.language == language,
        )
    ).scalar_one()


def test_stage_complete_manifest_is_execution_owned_ordered_and_inactive(
    activation_session_factory: sessionmaker[Session],
) -> None:
    translation_imports = _translation_imports()
    identity, repository_id = _seed_running_direct_import(activation_session_factory)
    reference = _reference(repository_id)

    manifest = translation_imports.stage_translation_parse(
        activation_session_factory,
        identity=identity,
        references=(reference,),
        result=_direct_result(),
    )

    assert manifest.execution_id == identity.execution_id
    assert manifest.value_count == 2
    assert manifest.issue_count == 0
    assert len(manifest.digest) == 64
    with activation_session_factory() as session:
        source_rows = tuple(
            session.scalars(
                select(ImportSourceReference)
                .where(ImportSourceReference.execution_id == identity.execution_id)
                .order_by(ImportSourceReference.position)
            )
        )
        staged_rows = tuple(
            session.scalars(
                select(StagedTranslationValue)
                .where(StagedTranslationValue.import_execution_id == identity.execution_id)
                .order_by(StagedTranslationValue.position)
            )
        )
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
    assert [(row.position, row.path) for row in source_rows] == [(0, "locales.json")]
    assert [(row.position, row.language, row.raw_key) for row in staged_rows] == [
        (0, "en", "welcome"),
        (1, "it", "welcome"),
    ]
    assert scope is not None
    assert scope.active_execution_id is None
    assert scope.dataset_version == 0


def test_stage_parser_failure_records_only_bounded_safe_issues(
    activation_session_factory: sessionmaker[Session],
) -> None:
    translation_imports = _translation_imports()
    identity, repository_id = _seed_running_direct_import(activation_session_factory)
    reference = _reference(repository_id)
    result = CanonicalParseResult(
        issues=(
            CanonicalIssue(
                code="malformed_file",
                repository_side="direct",
                path="locales.json",
                message="Canonical parser input is invalid.",
            ),
        )
    )

    manifest = translation_imports.stage_translation_parse(
        activation_session_factory,
        identity=identity,
        references=(reference,),
        result=result,
    )

    assert manifest.value_count == 0
    assert manifest.issue_count == 1
    with activation_session_factory() as session:
        staged_count = len(
            tuple(
                session.scalars(
                    select(StagedTranslationValue).where(
                        StagedTranslationValue.import_execution_id == identity.execution_id
                    )
                )
            )
        )
        issues = tuple(
            session.scalars(
                select(TranslationParseIssue).where(
                    TranslationParseIssue.import_execution_id == identity.execution_id
                )
            )
        )
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
    assert staged_count == 0
    assert [(issue.issue_code, issue.message) for issue in issues] == [
        ("malformed_file", "Canonical parser input is invalid.")
    ]
    assert scope is None or scope.active_execution_id is None


def test_stage_rejects_a_late_noncurrent_execution_without_rows(
    activation_session_factory: sessionmaker[Session],
) -> None:
    translation_imports = _translation_imports()
    identity, repository_id = _seed_running_direct_import(activation_session_factory)
    with activation_session_factory.begin() as session:
        execution = session.get_one(ImportExecution, identity.execution_id)
        job = session.get_one(ImportJob, identity.import_id)
        execution.state = "failed"
        execution.finished_at = datetime.now(UTC)
        job.state = "import_failed"
        job.error_category = "bounded_failure"
        job.error_message = "Import failed."

    manifest = translation_imports.stage_translation_parse(
        activation_session_factory,
        identity=identity,
        references=(_reference(repository_id),),
        result=_direct_result(),
    )

    assert manifest is None
    with activation_session_factory() as session:
        assert (
            session.scalar(
                select(ImportSourceReference).where(
                    ImportSourceReference.execution_id == identity.execution_id
                )
            )
            is None
        )
        assert (
            session.scalar(
                select(StagedTranslationValue).where(
                    StagedTranslationValue.import_execution_id == identity.execution_id
                )
            )
            is None
        )


def test_worker_processing_result_requires_exact_canonical_manifest_digest() -> None:
    fields = import_jobs.ImportProcessingResult.__dataclass_fields__
    assert tuple(fields) == ("references", "movement", "canonical_manifest_digest")


def test_refresh_move_preserves_uuid_state_constraint_and_history(
    activation_session_factory: sessionmaker[Session],
) -> None:
    identity, repository_id = _seed_running_direct_import(activation_session_factory)
    _reconcile_staged_result(
        activation_session_factory,
        identity=identity,
        repository_id=repository_id,
        result=_json_result(),
    )
    actor_id = uuid4()
    with activation_session_factory.begin() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
        assert scope is not None
        value = _value_for(
            session,
            scope_id=scope.id,
            raw_key="welcome",
            language="it",
        )
        value.review_state = "approved"
        session.add(
            User(
                id=actor_id,
                email=f"move-{actor_id}@example.com",
                display_name="Move reviewer",
                hashed_password="not-used-by-import-tests",
                is_active=True,
                must_change_password=False,
            )
        )
        session.add(
            TranslationConstraint(
                scope_id=scope.id,
                translation_key_id=value.translation_key_id,
                language="it",
                max_chars=4,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        original_value_id = value.id
        original_key_id = value.translation_key_id
        original_revision_ids = tuple(
            session.scalars(
                select(TranslationValueRevision.id).where(
                    TranslationValueRevision.value_id == value.id
                )
            )
        )

    successor = _start_refresh_execution(activation_session_factory, identity)
    _reconcile_staged_result(
        activation_session_factory,
        identity=successor,
        repository_id=repository_id,
        result=_json_result(path="moved/locales.json"),
        path="moved/locales.json",
        commit_hash="c" * 40,
    )

    with activation_session_factory() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
        assert scope is not None
        value = _value_for(
            session,
            scope_id=scope.id,
            raw_key="welcome",
            language="it",
        )
        locator = session.get_one(TranslationValueLocator, value.id)
        constraint = session.scalar(
            select(TranslationConstraint).where(
                TranslationConstraint.translation_key_id == value.translation_key_id,
                TranslationConstraint.language == "it",
            )
        )
        revision_ids = tuple(
            session.scalars(
                select(TranslationValueRevision.id).where(
                    TranslationValueRevision.value_id == value.id
                )
            )
        )
    assert value.id == original_value_id
    assert value.translation_key_id == original_key_id
    assert value.review_state == "approved"
    assert locator.path == "moved/locales.json"
    assert constraint is not None and constraint.max_chars == 4
    assert revision_ids == original_revision_ids


def test_refresh_rename_is_old_tombstone_plus_unrelated_new_draft(
    activation_session_factory: sessionmaker[Session],
) -> None:
    identity, repository_id = _seed_running_direct_import(activation_session_factory)
    _reconcile_staged_result(
        activation_session_factory,
        identity=identity,
        repository_id=repository_id,
        result=_json_result(),
    )
    with activation_session_factory() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
        assert scope is not None
        old_value_id = _value_for(
            session,
            scope_id=scope.id,
            raw_key="welcome",
            language="it",
        ).id

    successor = _start_refresh_execution(activation_session_factory, identity)
    _reconcile_staged_result(
        activation_session_factory,
        identity=successor,
        repository_id=repository_id,
        result=_json_result(raw_key="greeting"),
        commit_hash="c" * 40,
    )

    with activation_session_factory() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
        assert scope is not None
        old_key = session.scalar(
            select(TranslationKey).where(
                TranslationKey.scope_id == scope.id,
                TranslationKey.raw_key == "welcome",
            )
        )
        new_key = session.scalar(
            select(TranslationKey).where(
                TranslationKey.scope_id == scope.id,
                TranslationKey.raw_key == "greeting",
            )
        )
        assert old_key is not None and new_key is not None
        old_value = _value_for(
            session,
            scope_id=scope.id,
            raw_key="welcome",
            language="it",
        )
        new_value = _value_for(
            session,
            scope_id=scope.id,
            raw_key="greeting",
            language="it",
        )
    assert old_key.is_deleted is True
    assert old_value.is_deleted is True
    assert old_value.id == old_value_id
    assert new_key.id != old_key.id
    assert new_value.id != old_value.id
    assert new_value.review_state == "draft"


def test_refresh_complete_absence_tombstones_without_losing_context(
    activation_session_factory: sessionmaker[Session],
) -> None:
    identity, repository_id = _seed_running_direct_import(activation_session_factory)
    _reconcile_staged_result(
        activation_session_factory,
        identity=identity,
        repository_id=repository_id,
        result=_json_result(),
    )
    with activation_session_factory.begin() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
        assert scope is not None
        value = _value_for(
            session,
            scope_id=scope.id,
            raw_key="welcome",
            language="it",
        )
        value.review_state = "rejected"
        original_value_id = value.id
        original_locator_id = value.locator.value_id if value.locator is not None else None
        original_revision_count = len(value.revisions)

    successor = _start_refresh_execution(activation_session_factory, identity)
    _reconcile_staged_result(
        activation_session_factory,
        identity=successor,
        repository_id=repository_id,
        result=CanonicalParseResult(),
        commit_hash="c" * 40,
    )

    with activation_session_factory() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
        assert scope is not None
        value = _value_for(
            session,
            scope_id=scope.id,
            raw_key="welcome",
            language="it",
        )
        key = session.get_one(TranslationKey, value.translation_key_id)
        revision_count = session.scalar(
            select(text("count(*)"))
            .select_from(TranslationValueRevision)
            .where(TranslationValueRevision.value_id == value.id)
        )
    assert value.id == original_value_id
    assert value.review_state == "rejected"
    assert value.is_deleted is True and value.deleted_at is not None
    assert key.is_deleted is True and key.deleted_at is not None
    assert value.locator is not None and value.locator.value_id == original_locator_id
    assert revision_count == original_revision_count + 1


def test_refresh_external_change_requires_exact_correlation_to_preserve_approved(
    activation_session_factory: sessionmaker[Session],
) -> None:
    identity, repository_id = _seed_running_direct_import(activation_session_factory)
    initial = _json_result()
    target = next(value for value in initial.values if value.language == "it")
    correlation_key = (
        repository_id,
        target.logical_key,
        target.language,
        canonical_selector_bytes(target.selector),
    )
    _reconcile_staged_result(
        activation_session_factory,
        identity=identity,
        repository_id=repository_id,
        result=initial,
        correlations={correlation_key: "submission:exact-123"},
    )
    with activation_session_factory.begin() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
        assert scope is not None
        _value_for(
            session,
            scope_id=scope.id,
            raw_key="welcome",
            language="it",
        ).review_state = "approved"

    uncorrelated = _start_refresh_execution(activation_session_factory, identity)
    _reconcile_staged_result(
        activation_session_factory,
        identity=uncorrelated,
        repository_id=repository_id,
        result=_json_result(translated="Salve"),
        commit_hash="c" * 40,
    )
    with activation_session_factory() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
        assert scope is not None
        value = _value_for(
            session,
            scope_id=scope.id,
            raw_key="welcome",
            language="it",
        )
        assert value.translated_text == "Salve"
        assert value.review_state == "draft"

    with activation_session_factory.begin() as session:
        value = session.get_one(TranslationValue, value.id)
        value.review_state = "approved"
    correlated = _start_refresh_execution(activation_session_factory, uncorrelated)
    correlated_result = _json_result(translated="Buongiorno")
    correlated_target = next(value for value in correlated_result.values if value.language == "it")
    correlated_key = (
        repository_id,
        correlated_target.logical_key,
        correlated_target.language,
        canonical_selector_bytes(correlated_target.selector),
    )
    _reconcile_staged_result(
        activation_session_factory,
        identity=correlated,
        repository_id=repository_id,
        result=correlated_result,
        commit_hash="d" * 40,
        correlations={correlated_key: "submission:exact-123"},
    )
    with activation_session_factory() as session:
        value = session.get_one(TranslationValue, value.id)
        assert value.translated_text == "Buongiorno"
        assert value.review_state == "approved"
        revisions = tuple(
            session.scalars(
                select(TranslationValueRevision)
                .where(TranslationValueRevision.value_id == value.id)
                .order_by(TranslationValueRevision.revision_number)
            )
        )
    assert [revision.correlation_reference for revision in revisions] == [
        "submission:exact-123",
        None,
        "submission:exact-123",
    ]


def test_refresh_source_change_resets_all_targets_and_preserves_target_text(
    activation_session_factory: sessionmaker[Session],
) -> None:
    identity, repository_id = _seed_running_direct_import(activation_session_factory)
    _reconcile_staged_result(
        activation_session_factory,
        identity=identity,
        repository_id=repository_id,
        result=_json_result(),
    )
    with activation_session_factory.begin() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
        assert scope is not None
        target = _value_for(
            session,
            scope_id=scope.id,
            raw_key="welcome",
            language="it",
        )
        target.review_state = "approved"
        target_id = target.id
        initial_revision_count = len(target.revisions)

    successor = _start_refresh_execution(activation_session_factory, identity)
    _reconcile_staged_result(
        activation_session_factory,
        identity=successor,
        repository_id=repository_id,
        result=_json_result(source="Hello again"),
        commit_hash="c" * 40,
    )

    with activation_session_factory() as session:
        target = session.get_one(TranslationValue, target_id)
        revision_count = session.scalar(
            select(text("count(*)"))
            .select_from(TranslationValueRevision)
            .where(TranslationValueRevision.value_id == target.id)
        )
    assert target.source_text == "Hello again"
    assert target.translated_text == "Ciao"
    assert target.review_state == "draft"
    assert revision_count == initial_revision_count + 1
