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
    TranslationParseIssue,
)
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
