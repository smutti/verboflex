"""Execution-scoped canonical translation staging and activation seams."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from sqlalchemy import insert, select, text, update
from sqlalchemy.orm import Session, selectinload, sessionmaker

from verboflex.localization.duplicate_diagnostics import duplicate_identity_digest
from verboflex.localization.graphemes import grapheme_count
from verboflex.localization.importing.core import (
    MAX_CANONICAL_ISSUES,
    CanonicalParseResult,
    canonical_result_is_valid,
    canonical_selector_bytes,
    canonical_selector_digest,
)
from verboflex.models.duplicate_report import DuplicateGroupRow, DuplicateReportRow
from verboflex.models.import_job import ImportExecution, ImportJob, ImportSourceReference
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.translation import (
    LocalizationScope,
    StagedTranslationValue,
    TranslationKey,
    TranslationParseIssue,
    TranslationValue,
    TranslationValueLocator,
    TranslationValueRevision,
)
from verboflex.services.translation_constraints import recompute_translation_constraints

if TYPE_CHECKING:
    from verboflex.services.import_jobs import (
        ImportExecutionIdentity,
        ImportSourceReferenceRecord,
        RepositoryRole,
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
    code_catalog: dict[str, object] | None = None,
    correlation_references: Mapping[CorrelationIdentity, str] | None = None,
) -> StagedParseManifest | None:
    """Persist one immutable inactive parse result for an exact running execution."""
    if not canonical_result_is_valid(result, mapping=True):
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
        execution.code_catalog = code_catalog
        validated_references = _validate_references(identity=identity, references=references)
        reference_by_locator = {
            (reference.repository_side, reference.path): reference
            for reference in validated_references
        }
        _reject_existing_staging(session, execution_id=execution.id)

        scope: LocalizationScope | None = None
        if not result.issues:
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
            session.add(
                StagedTranslationValue(
                    import_execution_id=execution.id,
                    import_job_id=job.id,
                    scope_id=scope.id,
                    **payload,
                )
            )
            if (position + 1) % 500 == 0:
                session.flush()

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
        digest = staged_manifest_digest(session, identity=identity)
        return StagedParseManifest(
            execution_id=execution.id,
            digest=digest,
            value_count=len(result.values),
            issue_count=len(issue_payloads),
        )


def staged_manifest_digest(
    session: Session,
    *,
    identity: ImportExecutionIdentity,
) -> str:
    """Rebuild the deterministic digest of durable immutable staging rows."""
    from verboflex.services.import_jobs import ImportSourceReferenceRecord

    references = tuple(
        session.scalars(
            select(ImportSourceReference)
            .where(ImportSourceReference.execution_id == identity.execution_id)
            .order_by(ImportSourceReference.position)
        )
    )
    staged_values = session.scalars(
        select(StagedTranslationValue)
        .where(StagedTranslationValue.import_execution_id == identity.execution_id)
        .order_by(StagedTranslationValue.position)
        .execution_options(yield_per=500)
    )
    issues = tuple(
        session.scalars(
            select(TranslationParseIssue)
            .where(TranslationParseIssue.import_execution_id == identity.execution_id)
            .order_by(TranslationParseIssue.position)
        )
    )
    reference_records = tuple(
        ImportSourceReferenceRecord(
            position=reference.position,
            repository_side=cast("RepositoryRole", reference.repository_side),
            repository_id=reference.repository_id,
            source_branch=reference.source_branch,
            commit_hash=reference.commit_hash,
            path=reference.path,
            size_bytes=reference.size_bytes,
            sha256=reference.sha256,
        )
        for reference in references
    )
    digest = _manifest_digest(
        identity=identity,
        references=reference_records,
        values=(_staged_payload(value) for value in staged_values),
        issues=[
            {
                "column": issue.column,
                "issue_code": issue.issue_code,
                "line": issue.line,
                "message": issue.message,
                "path": issue.path,
                "position": issue.position,
                "repository_side": issue.repository_side,
            }
            for issue in issues
        ],
    )

    catalog = session.get_one(ImportExecution, identity.execution_id).code_catalog
    if catalog is None:
        return digest
    encoded = json.dumps(catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256((digest + encoded).encode("ascii")).hexdigest()


def require_complete_staged_manifest(
    session: Session,
    *,
    identity: ImportExecutionIdentity,
    manifest_digest: str,
) -> tuple[StagedTranslationValue, ...]:
    """Rebuild and verify the complete immutable candidate before reconciliation."""
    if (
        not isinstance(manifest_digest, str)
        or len(manifest_digest) != 64
        or any(character not in "0123456789abcdef" for character in manifest_digest)
    ):
        raise TranslationImportRejected("canonical manifest digest rejected")
    references = tuple(
        session.scalars(
            select(ImportSourceReference)
            .where(ImportSourceReference.execution_id == identity.execution_id)
            .order_by(ImportSourceReference.position)
        )
    )
    staged_values = tuple(
        session.scalars(
            select(StagedTranslationValue)
            .where(StagedTranslationValue.import_execution_id == identity.execution_id)
            .order_by(StagedTranslationValue.position)
        )
    )
    issues = tuple(
        session.scalars(
            select(TranslationParseIssue)
            .where(TranslationParseIssue.import_execution_id == identity.execution_id)
            .order_by(TranslationParseIssue.position)
        )
    )
    if (
        not references
        or issues
        or tuple(reference.position for reference in references) != tuple(range(len(references)))
        or tuple(value.position for value in staged_values) != tuple(range(len(staged_values)))
        or any(
            value.import_job_id != identity.import_id
            or value.import_execution_id != identity.execution_id
            for value in staged_values
        )
    ):
        raise TranslationImportRejected("canonical staged manifest is incomplete")
    from verboflex.services.import_jobs import ImportSourceReferenceRecord

    reference_records = tuple(
        ImportSourceReferenceRecord(
            position=reference.position,
            repository_side=cast("RepositoryRole", reference.repository_side),
            repository_id=reference.repository_id,
            source_branch=reference.source_branch,
            commit_hash=reference.commit_hash,
            path=reference.path,
            size_bytes=reference.size_bytes,
            sha256=reference.sha256,
        )
        for reference in references
    )
    _validate_references(identity=identity, references=reference_records)
    digest = staged_manifest_digest(session, identity=identity)
    if digest != manifest_digest:
        raise TranslationImportRejected("canonical staged manifest digest mismatch")
    return staged_values


def reconcile_canonical_translations(
    session: Session,
    *,
    identity: ImportExecutionIdentity,
    scope: LocalizationScope,
    manifest_digest: str,
    now: datetime | None = None,
) -> ReconciliationResult:
    """Reconcile one complete staged candidate by stable semantic identity."""
    mapping = session.get(ProductRepositoryMapping, identity.mapping_id)
    if mapping is None or mapping.base_language is None:
        raise TranslationImportRejected("canonical base language is unavailable")
    if (
        scope.product_id != identity.product_id
        or scope.mapping_identity_key != mapping.identity_key
    ):
        raise TranslationImportRejected("canonical scope authority rejected")
    staged_values = require_complete_staged_manifest(
        session,
        identity=identity,
        manifest_digest=manifest_digest,
    )
    reference_by_position = {
        reference.position: reference
        for reference in session.scalars(
            select(ImportSourceReference).where(
                ImportSourceReference.execution_id == identity.execution_id
            )
        )
    }
    reconciled_at = now or datetime.now(UTC)

    existing_keys = tuple(
        session.scalars(
            select(TranslationKey)
            .options(
                selectinload(TranslationKey.values).selectinload(TranslationValue.locator),
                selectinload(TranslationKey.values).selectinload(TranslationValue.revisions),
                selectinload(TranslationKey.constraints),
            )
            .where(TranslationKey.scope_id == scope.id)
            .with_for_update()
        )
    )
    key_by_identity = {
        (key.repository_id, key.configured_branch, key.raw_key): key for key in existing_keys
    }
    quarantined_groups = _complete_duplicate_groups(session, execution_id=identity.execution_id)
    if not existing_keys:
        return _insert_initial_dataset(
            session,
            identity=identity,
            scope=scope,
            staged_values=staged_values,
            references=reference_by_position,
            now=reconciled_at,
        )
    source_changed_raw_keys: set[str] = set()
    for staged in staged_values:
        if staged.language != mapping.base_language:
            continue
        key = key_by_identity.get((staged.repository_id, staged.configured_branch, staged.raw_key))
        if key is None:
            source_changed_raw_keys.add(staged.raw_key)
            continue
        current = next(
            (
                value
                for value in key.values
                if value.language == staged.language
                and value.selector_version == staged.selector_version
                and value.selector_digest == staged.selector_digest
            ),
            None,
        )
        if current is None or current.source_text != staged.source_text:
            source_changed_raw_keys.add(staged.raw_key)
    seen_key_ids: set[UUID] = set()
    seen_value_ids: set[UUID] = set()
    created_value_ids: list[UUID] = []
    updated_value_ids: list[UUID] = []
    tombstoned_value_ids: list[UUID] = []
    affected_value_ids: set[UUID] = set()

    for staged in staged_values:
        reference = reference_by_position.get(staged.source_reference_position)
        if reference is None:
            raise TranslationImportRejected("canonical source provenance rejected")
        key_identity = (staged.repository_id, staged.configured_branch, staged.raw_key)
        key = key_by_identity.get(key_identity)
        if key is None:
            key = TranslationKey(
                id=uuid4(),
                scope_id=scope.id,
                product_id=scope.product_id,
                repository_id=staged.repository_id,
                configured_branch=staged.configured_branch,
                raw_key=staged.raw_key,
                values=[],
                constraints=[],
            )
            session.add(key)
            key_by_identity[key_identity] = key
        elif key.is_deleted:
            key.is_deleted = False
            key.deleted_at = None
        seen_key_ids.add(key.id)

        value_by_identity = {
            (value.language, value.selector_version, value.selector_digest): value
            for value in key.values
        }
        value_identity = (
            staged.language,
            staged.selector_version,
            staged.selector_digest,
        )
        value = value_by_identity.get(value_identity)
        parser_deleted = _staged_value_is_deleted(staged)
        if value is None:
            value = TranslationValue(
                id=uuid4(),
                scope_id=scope.id,
                translation_key_id=key.id,
                language=staged.language,
                selector_version=staged.selector_version,
                selector_kind=staged.selector_kind,
                selector_bytes=staged.selector_bytes,
                selector_digest=staged.selector_digest,
                source_text=staged.source_text,
                translated_text=staged.translated_text,
                display_text=staged.display_text,
                structure=staged.structure,
                review_state="draft",
                is_deleted=parser_deleted,
                deleted_at=reconciled_at if parser_deleted else None,
                revisions=[],
                locator=None,
            )
            session.add(value)
            key.values.append(value)
            created_value_ids.append(value.id)
            affected_value_ids.add(value.id)
            _append_value_revision(
                session,
                value=value,
                identity=identity,
                staged=staged,
                reference=reference,
                revision_number=1,
                review_state=value.review_state,
                is_deleted=value.is_deleted,
                deleted_at=value.deleted_at,
            )
        else:
            source_changed = value.source_text != staged.source_text or (
                value.language != mapping.base_language
                and staged.raw_key in source_changed_raw_keys
            )
            content_changed = (
                value.source_text != staged.source_text
                or value.translated_text != staged.translated_text
                or value.display_text != staged.display_text
                or value.structure != staged.structure
                or source_changed
            )
            target_changed = value.translated_text != staged.translated_text
            deletion_changed = value.is_deleted != parser_deleted
            next_review_state = value.review_state
            latest_revision = max(
                value.revisions,
                key=lambda revision: revision.revision_number,
                default=None,
            )
            current_target_is_untracked = (
                latest_revision is not None
                and latest_revision.translated_text != value.translated_text
            )
            if source_changed and value.language != mapping.base_language:
                next_review_state = "draft"
            elif target_changed or current_target_is_untracked:
                exact_correlation = (
                    value.review_state == "approved"
                    and staged.correlation_reference is not None
                    and any(
                        revision.correlation_reference == staged.correlation_reference
                        and revision.source_text == staged.source_text
                        and revision.translated_text == staged.translated_text
                        and revision.display_text == staged.display_text
                        and revision.structure == staged.structure
                        and not revision.is_deleted
                        for revision in value.revisions
                    )
                )
                if not exact_correlation:
                    next_review_state = "draft"
            elif value.is_deleted and not parser_deleted:
                next_review_state = "draft"

            if content_changed or deletion_changed or next_review_state != value.review_state:
                _append_value_revision(
                    session,
                    value=value,
                    identity=identity,
                    staged=staged,
                    reference=reference,
                    revision_number=_next_revision_number(value),
                    review_state=next_review_state,
                    is_deleted=parser_deleted,
                    deleted_at=reconciled_at if parser_deleted else None,
                )
                value.source_text = staged.source_text
                value.translated_text = staged.translated_text
                value.display_text = staged.display_text
                value.structure = staged.structure
                value.review_state = next_review_state
                value.is_deleted = parser_deleted
                value.deleted_at = reconciled_at if parser_deleted else None
                updated_value_ids.append(value.id)
                affected_value_ids.add(value.id)

        seen_value_ids.add(value.id)
        _upsert_locator(
            session,
            value=value,
            identity=identity,
            staged=staged,
            reference=reference,
        )
        if (staged.position + 1) % 500 == 0:
            session.flush()

    for key in existing_keys:
        for value in key.values:
            if value.id in seen_value_ids or value.is_deleted:
                continue
            if _is_quarantined_value(
                key=key,
                value=value,
                groups=quarantined_groups,
            ):
                # Preserve the last unambiguous content and provenance. The
                # duplicate source occurrences remain diagnostic-only.
                seen_key_ids.add(key.id)
                continue
            reference = _tombstone_reference(
                reference_by_position,
                value=value,
            )
            _append_tombstone_revision(
                session,
                value=value,
                identity=identity,
                reference=reference,
                revision_number=_next_revision_number(value),
                deleted_at=reconciled_at,
            )
            value.is_deleted = True
            value.deleted_at = reconciled_at
            tombstoned_value_ids.append(value.id)
            affected_value_ids.add(value.id)
        if key.id not in seen_key_ids and not key.is_deleted:
            key.is_deleted = True
            key.deleted_at = reconciled_at

    for key in key_by_identity.values():
        all_values_deleted = bool(key.values) and all(value.is_deleted for value in key.values)
        if all_values_deleted and not key.is_deleted:
            key.is_deleted = True
            key.deleted_at = reconciled_at

    session.flush()
    recompute_translation_constraints(
        session,
        scope_id=scope.id,
        base_language=mapping.base_language,
    )
    return ReconciliationResult(
        created_value_ids=tuple(created_value_ids),
        updated_value_ids=tuple(updated_value_ids),
        tombstoned_value_ids=tuple(tombstoned_value_ids),
        affected_value_ids=tuple(sorted(affected_value_ids, key=str)),
    )


def _complete_duplicate_groups(
    session: Session, *, execution_id: UUID
) -> tuple[DuplicateGroupRow, ...]:
    report = session.scalar(
        select(DuplicateReportRow).where(
            DuplicateReportRow.execution_id == execution_id,
            DuplicateReportRow.complete.is_(True),
        )
    )
    if report is None:
        return ()
    return tuple(
        session.scalars(
            select(DuplicateGroupRow)
            .where(DuplicateGroupRow.report_id == report.id)
            .order_by(DuplicateGroupRow.position)
        )
    )


def _is_quarantined_value(
    *,
    key: TranslationKey,
    value: TranslationValue,
    groups: tuple[DuplicateGroupRow, ...],
) -> bool:
    locator = value.locator
    if locator is None:
        return False
    return any(
        group.repository_side == locator.repository_side
        and group.language == value.language
        and group.identity_digest
        == duplicate_identity_digest(
            locator.repository_side,
            group.layout_identity,
            value.language,
            key.raw_key,
            value.selector_digest,
        )
        for group in groups
    )


def _insert_initial_dataset(
    session: Session,
    *,
    identity: ImportExecutionIdentity,
    scope: LocalizationScope,
    staged_values: tuple[StagedTranslationValue, ...],
    references: Mapping[int, ImportSourceReference],
    now: datetime,
) -> ReconciliationResult:
    """Batch an empty scope without retaining a second full ORM object graph.

    The caller has verified the complete manifest and locked the scope. An empty
    scope has no keys or constraints (FK-owned), so initial constraint projection
    is exactly 'none'; refreshes continue through semantic reconciliation.
    """
    key_ids: dict[tuple[UUID, str, str], UUID] = {}
    all_deleted: dict[UUID, bool] = {}
    created: list[UUID] = []
    for offset in range(0, len(staged_values), 500):
        keys: list[dict[str, object]] = []
        values: list[dict[str, object]] = []
        revisions: list[dict[str, object]] = []
        locators: list[dict[str, object]] = []
        for staged in staged_values[offset : offset + 500]:
            reference = references.get(staged.source_reference_position)
            if reference is None:
                raise TranslationImportRejected("canonical source provenance rejected")
            natural_key = (staged.repository_id, staged.configured_branch, staged.raw_key)
            key_id = key_ids.get(natural_key)
            if key_id is None:
                key_id = uuid4()
                key_ids[natural_key] = key_id
                all_deleted[key_id] = True
                keys.append(
                    dict(
                        id=key_id,
                        scope_id=scope.id,
                        product_id=scope.product_id,
                        repository_id=staged.repository_id,
                        configured_branch=staged.configured_branch,
                        raw_key=staged.raw_key,
                        is_deleted=False,
                        deleted_at=None,
                    )
                )
            value_id = uuid4()
            deleted = _staged_value_is_deleted(staged)
            all_deleted[key_id] = all_deleted[key_id] and deleted
            common = dict(
                source_text=staged.source_text,
                translated_text=staged.translated_text,
                display_text=staged.display_text,
                structure=staged.structure,
                review_state="draft",
                is_deleted=deleted,
                deleted_at=now if deleted else None,
            )
            values.append(
                dict(
                    id=value_id,
                    scope_id=scope.id,
                    translation_key_id=key_id,
                    language=staged.language,
                    selector_version=staged.selector_version,
                    selector_kind=staged.selector_kind,
                    selector_bytes=staged.selector_bytes,
                    selector_digest=staged.selector_digest,
                    grapheme_count=grapheme_count(staged.display_text),
                    effective_max_chars=None,
                    effective_constraint_source="none",
                    is_over_limit=False,
                    **common,
                )
            )
            revisions.append(
                dict(
                    id=uuid4(),
                    value_id=value_id,
                    translation_key_id=key_id,
                    revision_number=1,
                    import_job_id=identity.import_id,
                    import_execution_id=identity.execution_id,
                    source_reference_position=reference.position,
                    source_commit_hash=reference.commit_hash,
                    correlation_reference=staged.correlation_reference,
                    **common,
                    revision_digest=_revision_digest(
                        value_id=value_id,
                        revision_number=1,
                        identity=identity,
                        source_reference_position=reference.position,
                        source_commit_hash=reference.commit_hash,
                        source_text=staged.source_text,
                        translated_text=staged.translated_text,
                        display_text=staged.display_text,
                        structure=staged.structure,
                        review_state="draft",
                        is_deleted=deleted,
                        correlation_reference=staged.correlation_reference,
                    ),
                )
            )
            locators.append(
                dict(
                    value_id=value_id,
                    translation_key_id=key_id,
                    import_job_id=identity.import_id,
                    import_execution_id=identity.execution_id,
                    source_reference_position=reference.position,
                    repository_side=staged.repository_side,
                    repository_id=staged.repository_id,
                    configured_branch=staged.configured_branch,
                    source_commit_hash=reference.commit_hash,
                    format=staged.format,
                    path=staged.path,
                    position=staged.locator_position,
                    structural_address=staged.structural_address,
                    line=staged.line,
                    column=staged.column,
                )
            )
            created.append(value_id)
        if keys:
            session.execute(insert(TranslationKey), keys)
        session.execute(insert(TranslationValue), values)
        session.execute(insert(TranslationValueRevision), revisions)
        session.execute(insert(TranslationValueLocator), locators)
    deleted_keys = [key_id for key_id, deleted in all_deleted.items() if deleted]
    for offset in range(0, len(deleted_keys), 500):
        session.execute(
            update(TranslationKey)
            .where(TranslationKey.id.in_(deleted_keys[offset : offset + 500]))
            .values(is_deleted=True, deleted_at=now)
        )
    return ReconciliationResult(
        created_value_ids=tuple(created),
        updated_value_ids=(),
        tombstoned_value_ids=(),
        affected_value_ids=tuple(sorted(created, key=str)),
    )


def activate_translation_dataset(
    session: Session,
    *,
    identity: ImportExecutionIdentity,
    scope: LocalizationScope,
    job: ImportJob,
    execution: ImportExecution,
    manifest_digest: str,
    now: datetime | None = None,
) -> ReconciliationResult:
    """Reconcile and expose one dataset with its exact source baseline atomically."""
    if (
        job.id != identity.import_id
        or job.current_execution_id != identity.execution_id
        or job.mapping_id != identity.mapping_id
        or job.revision_id != identity.revision_id
        or job.product_id != identity.product_id
        or job.state not in {"running", "current"}
        or execution.id != identity.execution_id
        or execution.import_job_id != identity.import_id
        or execution.sequence != identity.sequence
        or execution.connection_generation != identity.connection_generation
        or execution.state not in {"running", "succeeded"}
    ):
        raise TranslationImportRejected("canonical activation authority rejected")
    activated_at = now or datetime.now(UTC)
    result = reconcile_canonical_translations(
        session,
        identity=identity,
        scope=scope,
        manifest_digest=manifest_digest,
        now=activated_at,
    )
    execution.state = "succeeded"
    execution.finished_at = execution.finished_at or activated_at
    job.state = "current"
    job.active_baseline_execution_id = execution.id
    job.error_category = None
    job.error_message = None
    job.updated_at = activated_at
    session.flush()
    scope.current_revision_id = identity.revision_id
    scope.current_mapping_id = identity.mapping_id
    scope.active_import_job_id = job.id
    scope.active_execution_id = execution.id
    scope.dataset_version += 1
    session.flush()
    # Retired values and their history are transient reconciliation markers.
    # Purge only after complete manifest validation and successful activation,
    # in this same transaction; failure rolls back both activation and deletion.
    from verboflex.services.translation_purge import purge_retired_translations

    purge_retired_translations(session, scope_id=scope.id)
    from verboflex.services.translation_authoring import reconcile_authoring

    reconcile_authoring(session, scope_id=scope.id)
    # Compute repository coverage once in the import transaction, after pruning.
    # Workspace HTTP requests read this snapshot without scanning translations.
    session.execute(
        text("""UPDATE localization_scopes scope
            SET coverage_snapshot=verboflex_scope_coverage(scope.id, mapping.base_language),
                read_version=scope.read_version+1
            FROM product_repository_mappings mapping
            WHERE scope.id=:scope_id AND mapping.id=scope.current_mapping_id"""),
        {"scope_id": scope.id},
    )
    return result


def _staged_payload(value: StagedTranslationValue) -> dict[str, object]:
    return {
        "column": value.column,
        "configured_branch": value.configured_branch,
        "correlation_reference": value.correlation_reference,
        "display_text": value.display_text,
        "format": value.format,
        "language": value.language,
        "line": value.line,
        "locator_position": value.locator_position,
        "path": value.path,
        "position": value.position,
        "raw_key": value.raw_key,
        "repository_id": value.repository_id,
        "repository_side": value.repository_side,
        "selector_bytes": value.selector_bytes,
        "selector_digest": value.selector_digest,
        "selector_kind": value.selector_kind,
        "selector_version": value.selector_version,
        "source_reference_position": value.source_reference_position,
        "source_text": value.source_text,
        "structural_address": value.structural_address,
        "structure": value.structure,
        "translated_text": value.translated_text,
    }


def _staged_value_is_deleted(value: StagedTranslationValue) -> bool:
    for node in value.structure:
        if not isinstance(node, dict) or node.get("kind") != "qt_ts:translation":
            continue
        fields = node.get("fields")
        if not isinstance(fields, list):
            continue
        for field in fields:
            if (
                isinstance(field, dict)
                and field.get("name") == "deleted"
                and field.get("value") is True
            ):
                return True
    return False


def _next_revision_number(value: TranslationValue) -> int:
    return max((revision.revision_number for revision in value.revisions), default=0) + 1


def _revision_digest(
    *,
    value_id: UUID,
    revision_number: int,
    identity: ImportExecutionIdentity,
    source_reference_position: int,
    source_commit_hash: str,
    source_text: str | None,
    translated_text: str | None,
    display_text: str,
    structure: list[object],
    review_state: str,
    is_deleted: bool,
    correlation_reference: str | None,
) -> str:
    payload = {
        "correlation_reference": correlation_reference,
        "display_text": display_text,
        "execution_id": str(identity.execution_id),
        "is_deleted": is_deleted,
        "revision_number": revision_number,
        "review_state": review_state,
        "source_commit_hash": source_commit_hash,
        "source_reference_position": source_reference_position,
        "source_text": source_text,
        "structure": structure,
        "translated_text": translated_text,
        "value_id": str(value_id),
        "version": 1,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _append_value_revision(
    session: Session,
    *,
    value: TranslationValue,
    identity: ImportExecutionIdentity,
    staged: StagedTranslationValue,
    reference: ImportSourceReference,
    revision_number: int,
    review_state: str,
    is_deleted: bool,
    deleted_at: datetime | None,
) -> None:
    revision = TranslationValueRevision(
        id=uuid4(),
        value_id=value.id,
        translation_key_id=value.translation_key_id,
        revision_number=revision_number,
        revision_digest=_revision_digest(
            value_id=value.id,
            revision_number=revision_number,
            identity=identity,
            source_reference_position=reference.position,
            source_commit_hash=reference.commit_hash,
            source_text=staged.source_text,
            translated_text=staged.translated_text,
            display_text=staged.display_text,
            structure=staged.structure,
            review_state=review_state,
            is_deleted=is_deleted,
            correlation_reference=staged.correlation_reference,
        ),
        import_job_id=identity.import_id,
        import_execution_id=identity.execution_id,
        source_reference_position=reference.position,
        source_commit_hash=reference.commit_hash,
        source_text=staged.source_text,
        translated_text=staged.translated_text,
        display_text=staged.display_text,
        structure=staged.structure,
        review_state=review_state,
        is_deleted=is_deleted,
        deleted_at=deleted_at,
        correlation_reference=staged.correlation_reference,
    )
    value.revisions.append(revision)
    session.add(revision)


def _append_tombstone_revision(
    session: Session,
    *,
    value: TranslationValue,
    identity: ImportExecutionIdentity,
    reference: ImportSourceReference,
    revision_number: int,
    deleted_at: datetime,
) -> None:
    revision = TranslationValueRevision(
        id=uuid4(),
        value_id=value.id,
        translation_key_id=value.translation_key_id,
        revision_number=revision_number,
        revision_digest=_revision_digest(
            value_id=value.id,
            revision_number=revision_number,
            identity=identity,
            source_reference_position=reference.position,
            source_commit_hash=reference.commit_hash,
            source_text=value.source_text,
            translated_text=value.translated_text,
            display_text=value.display_text,
            structure=value.structure,
            review_state=value.review_state,
            is_deleted=True,
            correlation_reference=None,
        ),
        import_job_id=identity.import_id,
        import_execution_id=identity.execution_id,
        source_reference_position=reference.position,
        source_commit_hash=reference.commit_hash,
        source_text=value.source_text,
        translated_text=value.translated_text,
        display_text=value.display_text,
        structure=value.structure,
        review_state=value.review_state,
        is_deleted=True,
        deleted_at=deleted_at,
        correlation_reference=None,
    )
    value.revisions.append(revision)
    session.add(revision)


def _upsert_locator(
    session: Session,
    *,
    value: TranslationValue,
    identity: ImportExecutionIdentity,
    staged: StagedTranslationValue,
    reference: ImportSourceReference,
) -> None:
    locator = value.locator
    if locator is None:
        locator = TranslationValueLocator(
            value_id=value.id,
            translation_key_id=value.translation_key_id,
            import_job_id=identity.import_id,
            import_execution_id=identity.execution_id,
            source_reference_position=reference.position,
            repository_side=staged.repository_side,
            repository_id=staged.repository_id,
            configured_branch=staged.configured_branch,
            source_commit_hash=reference.commit_hash,
            format=staged.format,
            path=staged.path,
            position=staged.locator_position,
            structural_address=staged.structural_address,
            line=staged.line,
            column=staged.column,
        )
        value.locator = locator
        session.add(locator)
        return
    locator.import_job_id = identity.import_id
    locator.import_execution_id = identity.execution_id
    locator.source_reference_position = reference.position
    locator.repository_side = staged.repository_side
    locator.repository_id = staged.repository_id
    locator.configured_branch = staged.configured_branch
    locator.source_commit_hash = reference.commit_hash
    locator.format = staged.format
    locator.path = staged.path
    locator.position = staged.locator_position
    locator.structural_address = staged.structural_address
    locator.line = staged.line
    locator.column = staged.column


def _tombstone_reference(
    references: Mapping[int, ImportSourceReference],
    *,
    value: TranslationValue,
) -> ImportSourceReference:
    locator = value.locator
    candidates = tuple(
        reference
        for _, reference in sorted(references.items())
        if locator is not None
        and reference.repository_id == locator.repository_id
        and reference.source_branch == locator.configured_branch
    )
    if not candidates:
        raise TranslationImportRejected("canonical tombstone provenance rejected")
    return candidates[0]


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
        or tuple(
            (side.role, side.repository_id, side.source_branch, side.localization_root)
            for side in mapping.sides
        )
        != tuple(
            (side.role, side.repository_id, side.source_branch, side.localization_root)
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
    roots = {side.role: side.localization_root for side in identity.repository_sides}
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
            or (
                roots.get(reference.repository_side) is not None
                and not reference.path.startswith(str(roots[reference.repository_side]) + "/")
            )
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
    return scope


def _manifest_digest(
    *,
    identity: ImportExecutionIdentity,
    references: tuple[ImportSourceReferenceRecord, ...],
    values: Iterable[dict[str, object]],
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
    }
    header = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(header[:-1] + b',"values":[')
    for position, value in enumerate(values):
        if position:
            digest.update(b",")
        digest.update(
            json.dumps(
                {
                    **value,
                    "repository_id": str(value["repository_id"]),
                    "selector_bytes": cast(bytes, value["selector_bytes"]).decode("utf-8"),
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
    digest.update(b'],"version":1}')
    return digest.hexdigest()
