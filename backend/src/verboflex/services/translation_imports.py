"""Execution-scoped canonical translation staging and activation seams."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from verboflex.localization.importing.core import (
    MAX_CANONICAL_ISSUES,
    CanonicalParseResult,
    canonical_result_is_valid,
    canonical_selector_bytes,
    canonical_selector_digest,
)
from verboflex.models.import_job import ImportExecution, ImportJob, ImportSourceReference
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.translation import (
    LocalizationScope,
    StagedTranslationValue,
    TranslationParseIssue,
)

if TYPE_CHECKING:
    from verboflex.services.import_jobs import (
        ImportExecutionIdentity,
        ImportSourceReferenceRecord,
    )

CorrelationIdentity = tuple[UUID, str, str, bytes]


@dataclass(frozen=True, slots=True)
class StagedParseManifest:
    """Digest-bound inactive parser outcome owned by one immutable execution."""

    execution_id: UUID
    digest: str
    value_count: int
    issue_count: int

    @property
    def complete(self) -> bool:
        return self.issue_count == 0


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Stable identities touched by one complete canonical reconciliation."""

    created_value_ids: tuple[UUID, ...]
    updated_value_ids: tuple[UUID, ...]
    tombstoned_value_ids: tuple[UUID, ...]
    affected_value_ids: tuple[UUID, ...]


class TranslationImportRejected(ValueError):
    """Raised when staged canonical authority is incomplete or inconsistent."""


def stage_translation_parse(
    factory: sessionmaker[Session],
    *,
    identity: ImportExecutionIdentity,
    references: tuple[ImportSourceReferenceRecord, ...],
    result: CanonicalParseResult,
    correlation_references: Mapping[CorrelationIdentity, str] | None = None,
) -> StagedParseManifest | None:
    """Persist one immutable inactive parse result for an exact running execution."""
    if not canonical_result_is_valid(result):
        raise TranslationImportRejected("canonical parser result rejected")
    correlations = correlation_references or {}
    if any(
        not isinstance(value, str) or not 1 <= len(value) <= 256 for value in correlations.values()
    ):
        raise TranslationImportRejected("canonical correlation rejected")

    with factory.begin() as session:
        authority = _lock_current_staging_authority(session, identity=identity)
        if authority is None:
            return None
        mapping, job, execution = authority
        validated_references = _validate_references(identity=identity, references=references)
        reference_by_locator = {
            (reference.repository_side, reference.path): reference
            for reference in validated_references
        }
        _reject_existing_staging(session, execution_id=execution.id)

        scope: LocalizationScope | None = None
        if result.values:
            scope = _get_or_create_scope(
                session,
                identity=identity,
                mapping=mapping,
            )
        for reference in validated_references:
            session.add(
                ImportSourceReference(
                    execution_id=execution.id,
                    position=reference.position,
                    repository_side=reference.repository_side,
                    repository_id=reference.repository_id,
                    source_branch=reference.source_branch,
                    commit_hash=reference.commit_hash,
                    path=reference.path,
                    size_bytes=reference.size_bytes,
                    sha256=reference.sha256,
                )
            )
        session.flush()

        staged_payloads: list[dict[str, object]] = []
        for position, value in enumerate(result.values):
            matched_reference = reference_by_locator.get(
                (value.locator.repository_side, value.locator.path)
            )
            if matched_reference is None or scope is None:
                raise TranslationImportRejected("canonical source reference rejected")
            selector_bytes = canonical_selector_bytes(value.selector)
            correlation_reference = correlations.get(
                (
                    matched_reference.repository_id,
                    value.logical_key,
                    value.language,
                    selector_bytes,
                )
            )
            payload: dict[str, object] = {
                "configured_branch": matched_reference.source_branch,
                "correlation_reference": correlation_reference,
                "display_text": value.display_text,
                "format": value.locator.format,
                "language": value.language,
                "line": value.locator.line,
                "column": value.locator.column,
                "locator_position": value.locator.position,
                "path": value.locator.path,
                "position": position,
                "raw_key": value.logical_key,
                "repository_id": matched_reference.repository_id,
                "repository_side": value.locator.repository_side,
                "selector_bytes": selector_bytes,
                "selector_digest": canonical_selector_digest(value.selector),
                "selector_kind": value.selector.kind,
                "selector_version": value.selector.schema_version,
                "source_reference_position": matched_reference.position,
                "source_text": value.source_text,
                "structural_address": list(value.locator.structural_address),
                "structure": [node.to_mapping() for node in value.structure],
                "translated_text": value.translated_text,
            }
            staged_payloads.append(payload)
            session.add(
                StagedTranslationValue(
                    import_execution_id=execution.id,
                    import_job_id=job.id,
                    scope_id=scope.id,
                    **payload,
                )
            )

        issue_payloads: list[dict[str, object]] = []
        for position, issue in enumerate(result.issues[:MAX_CANONICAL_ISSUES]):
            issue_payload: dict[str, object] = {
                "column": issue.column,
                "issue_code": issue.code,
                "line": issue.line,
                "message": issue.message,
                "path": issue.path,
                "position": position,
                "repository_side": issue.repository_side,
            }
            issue_payloads.append(issue_payload)
            session.add(
                TranslationParseIssue(
                    import_execution_id=execution.id,
                    import_job_id=job.id,
                    **issue_payload,
                )
            )
        session.flush()
        digest = _manifest_digest(
            identity=identity,
            references=validated_references,
            values=staged_payloads,
            issues=issue_payloads,
        )
        return StagedParseManifest(
            execution_id=execution.id,
            digest=digest,
            value_count=len(staged_payloads),
            issue_count=len(issue_payloads),
        )


def _lock_current_staging_authority(
    session: Session,
    *,
    identity: ImportExecutionIdentity,
) -> tuple[ProductRepositoryMapping, ImportJob, ImportExecution] | None:
    product = session.execute(
        select(Product).where(Product.id == identity.product_id).with_for_update()
    ).scalar_one_or_none()
    revision = session.execute(
        select(ProductRevision)
        .where(
            ProductRevision.id == identity.revision_id,
            ProductRevision.product_id == identity.product_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    mapping = session.execute(
        select(ProductRepositoryMapping)
        .options(selectinload(ProductRepositoryMapping.sides))
        .where(
            ProductRepositoryMapping.id == identity.mapping_id,
            ProductRepositoryMapping.revision_id == identity.revision_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    job = session.execute(
        select(ImportJob).where(ImportJob.id == identity.import_id).with_for_update()
    ).scalar_one_or_none()
    execution = session.execute(
        select(ImportExecution)
        .where(
            ImportExecution.id == identity.execution_id,
            ImportExecution.import_job_id == identity.import_id,
            ImportExecution.sequence == identity.sequence,
            ImportExecution.connection_generation == identity.connection_generation,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if (
        product is None
        or not product.is_active
        or product.active_revision_id != identity.revision_id
        or revision is None
        or not revision.is_published
        or mapping is None
        or mapping.base_language is None
        or job is None
        or job.product_id != identity.product_id
        or job.revision_id != identity.revision_id
        or job.mapping_id != identity.mapping_id
        or job.topology != mapping.topology
        or job.current_execution_id != identity.execution_id
        or job.state != "running"
        or execution is None
        or execution.state != "running"
        or tuple((side.role, side.repository_id, side.source_branch) for side in mapping.sides)
        != tuple(
            (side.role, side.repository_id, side.source_branch)
            for side in identity.repository_sides
        )
    ):
        return None
    return mapping, job, execution


def _validate_references(
    *,
    identity: ImportExecutionIdentity,
    references: tuple[ImportSourceReferenceRecord, ...],
) -> tuple[ImportSourceReferenceRecord, ...]:
    if type(references) is not tuple:
        raise TranslationImportRejected("canonical source references rejected")
    side_authority = {
        side.role: (side.repository_id, side.source_branch) for side in identity.repository_sides
    }
    seen: set[tuple[str, str]] = set()
    for position, reference in enumerate(references):
        authority = side_authority.get(reference.repository_side)
        if (
            reference.position != position
            or authority != (reference.repository_id, reference.source_branch)
            or len(reference.commit_hash) != 40
            or any(character not in "0123456789abcdef" for character in reference.commit_hash)
            or len(reference.sha256) != 64
            or any(character not in "0123456789abcdef" for character in reference.sha256)
            or reference.size_bytes < 0
            or not reference.path
            or reference.path.startswith("/")
            or ".." in reference.path.split("/")
            or (reference.repository_side, reference.path) in seen
        ):
            raise TranslationImportRejected("canonical source references rejected")
        seen.add((reference.repository_side, reference.path))
    return references


def _reject_existing_staging(session: Session, *, execution_id: UUID) -> None:
    if (
        session.scalar(
            select(StagedTranslationValue.import_execution_id)
            .where(StagedTranslationValue.import_execution_id == execution_id)
            .limit(1)
        )
        is not None
        or session.scalar(
            select(TranslationParseIssue.import_execution_id)
            .where(TranslationParseIssue.import_execution_id == execution_id)
            .limit(1)
        )
        is not None
        or session.scalar(
            select(ImportSourceReference.execution_id)
            .where(ImportSourceReference.execution_id == execution_id)
            .limit(1)
        )
        is not None
    ):
        raise TranslationImportRejected("canonical staging already exists")


def _get_or_create_scope(
    session: Session,
    *,
    identity: ImportExecutionIdentity,
    mapping: ProductRepositoryMapping,
) -> LocalizationScope:
    scope = session.execute(
        select(LocalizationScope)
        .where(
            LocalizationScope.product_id == identity.product_id,
            LocalizationScope.mapping_identity_key == mapping.identity_key,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if scope is None:
        scope = LocalizationScope(
            id=uuid4(),
            product_id=identity.product_id,
            mapping_identity_key=mapping.identity_key,
            current_revision_id=identity.revision_id,
            current_mapping_id=identity.mapping_id,
        )
        session.add(scope)
        session.flush()
    elif (
        scope.current_revision_id != identity.revision_id
        or scope.current_mapping_id != identity.mapping_id
    ):
        scope.current_revision_id = identity.revision_id
        scope.current_mapping_id = identity.mapping_id
        session.flush()
    return scope


def _manifest_digest(
    *,
    identity: ImportExecutionIdentity,
    references: tuple[ImportSourceReferenceRecord, ...],
    values: list[dict[str, object]],
    issues: list[dict[str, object]],
) -> str:
    payload = {
        "authority": {
            "connection_generation": identity.connection_generation,
            "execution_id": str(identity.execution_id),
            "import_id": str(identity.import_id),
            "mapping_id": str(identity.mapping_id),
            "product_id": str(identity.product_id),
            "revision_id": str(identity.revision_id),
            "sequence": identity.sequence,
        },
        "issues": issues,
        "references": [
            {
                "commit_hash": reference.commit_hash,
                "path": reference.path,
                "position": reference.position,
                "repository_id": str(reference.repository_id),
                "repository_side": reference.repository_side,
                "sha256": reference.sha256,
                "size_bytes": reference.size_bytes,
                "source_branch": reference.source_branch,
            }
            for reference in references
        ],
        "values": [
            {
                **payload,
                "repository_id": str(payload["repository_id"]),
                "selector_bytes": cast(bytes, payload["selector_bytes"]).decode("utf-8"),
            }
            for payload in values
        ],
        "version": 1,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
