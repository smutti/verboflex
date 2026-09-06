"""Published-mapping imports with durable UUID-only execution."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, NoReturn, Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker
from sqlalchemy.sql import Select

from verboflex.core.config import get_settings
from verboflex.integrations.bitbucket.client import (
    BitbucketCommitDelta,
    BitbucketFileDelta,
    BitbucketProviderReadError,
)
from verboflex.integrations.bitbucket.diagnostics import (
    BitbucketDiagnosticContext,
    log_bitbucket_operation_failure,
)
from verboflex.integrations.bitbucket.urls import (
    BitbucketOperation,
    repository_metadata_url,
    validate_provider_commit_hash,
    validate_repository_relative_path,
)
from verboflex.localization.importing.core import (
    CanonicalIssue,
    CanonicalParseResult,
    CanonicalParserInput,
)
from verboflex.localization.importing.registry import parse_canonical_mapping
from verboflex.localization.preview.core import (
    PreviewLayoutCandidate,
    layout_candidate_from_mapping,
)
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.import_job import (
    ImportExecution,
    ImportJob,
    ImportRewriteDelta,
    ImportRewriteProposal,
    ImportSourceReference,
)
from verboflex.models.preview_job import PreviewJob
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.repository import Repository
from verboflex.models.translation import LocalizationScope, TranslationParseIssue
from verboflex.services.bitbucket_oauth import PULLREQUEST_WRITE_SCOPE
from verboflex.services.preview_jobs import is_current_preview_confirmation
from verboflex.services.repositories import RepositoryRecord
from verboflex.services.repository_discovery import (
    SourceDiscoveryAdapter,
    discover_repository_sources_for_record,
)
from verboflex.services.translation_imports import (
    TranslationImportRejected,
    activate_translation_dataset,
    require_complete_staged_manifest,
    stage_translation_parse,
    staged_manifest_digest,
)

IMPORT_TASK_NAME = "verboflex.import.run"
IMPORT_WATCHDOG_BATCH_SIZE = 100
DEFAULT_IMPORT_PAGE_SIZE = 50
MAX_IMPORT_PAGE_SIZE = 100
MAX_IMPORT_CURSOR_LENGTH = 2048
_IMPORT_CURSOR_VERSION = 1
_IMPORT_ORDER_IDENTITY = "mapping_identity_v1"

ImportState = Literal[
    "not_imported",
    "queued",
    "running",
    "current",
    "may_be_stale",
    "review_required",
    "import_failed",
]
ImportCapability = Literal["ready", "reauthorization_required", "unavailable"]
ImportAction = Literal[
    "run_import",
    "refresh_import",
    "retry_import",
    "import_in_progress",
    "review_baseline_change",
]
ImportStatusFilter = Literal["all", "attention"]
ImportErrorCategory = Literal[
    "connection_required",
    "permission_denied",
    "rate_limited",
    "source_not_found",
    "timeout",
    "provider_unavailable",
    "bounded_failure",
]
RepositoryRole = Literal["direct", "keys", "translations"]
SourceMovementRelation = Literal["equal", "descendant", "diverged"]
SourceMovementKind = Literal["equal", "fast-forward", "review-required"]
RewriteDeltaChange = Literal["added", "modified", "removed"]
ImportDatasetStatusRecord = Literal["not_created", "active", "retained"]
ImportParserIssueCode = Literal[
    "malformed_file",
    "ambiguous_structure",
    "unsupported_structure",
    "duplicate_key",
    "base_language_required",
]
ImportParserIssueMessageKey = Literal[
    "import.parser.malformed_file",
    "import.parser.ambiguous_structure",
    "import.parser.unsupported_structure",
    "import.parser.duplicate_key",
    "import.parser.base_language_required",
]

MAX_PUBLIC_PARSER_ISSUES = 5
MAX_PUBLIC_PARSER_ISSUE_TOTAL = 500

_PARSER_ISSUE_MESSAGE_KEYS: dict[ImportParserIssueCode, ImportParserIssueMessageKey] = {
    "malformed_file": "import.parser.malformed_file",
    "ambiguous_structure": "import.parser.ambiguous_structure",
    "unsupported_structure": "import.parser.unsupported_structure",
    "duplicate_key": "import.parser.duplicate_key",
    "base_language_required": "import.parser.base_language_required",
}
_PARSER_ISSUE_SIDE_ORDER: dict[RepositoryRole, int] = {
    "direct": 0,
    "keys": 1,
    "translations": 2,
}


class ImportNotFound(LookupError):
    """Raised when published import authority is unavailable."""


class ImportConflict(ValueError):
    """Raised when persisted import state disagrees with current authority."""


class ImportAlreadyInProgress(ImportConflict):
    """Raised when one current execution is already queued or running."""


class ImportReviewRequired(ImportConflict):
    """Raised when a complete rewrite proposal awaits administrator review."""


class InvalidImportCursor(ValueError):
    """Raised when a cursor is malformed or belongs to another collection."""


class ImportConnectionUnavailable(RuntimeError):
    """Raised when the organizational connection cannot authorize a fresh read."""


class ImportRewriteStale(ImportConflict):
    """Raised when rewrite authority no longer matches the current mapping state."""


class ImportEnqueuer(Protocol):
    """Queue seam whose sole payload is the stable logical import UUID."""

    def __call__(self, import_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class ImportRepositorySideRecord:
    role: RepositoryRole
    repository_id: UUID
    source_branch: str
    localization_root: str | None = None


@dataclass(frozen=True, slots=True)
class ImportSourceReferenceRecord:
    position: int
    repository_side: RepositoryRole
    repository_id: UUID
    source_branch: str
    commit_hash: str
    path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ImportBaselineRecord:
    imported_at: datetime
    source_references: tuple[ImportSourceReferenceRecord, ...]


@dataclass(frozen=True, slots=True)
class ImportParserIssueRecord:
    """One public-safe parser diagnostic projected from immutable staging."""

    issue_code: ImportParserIssueCode
    repository_side: RepositoryRole
    path: str
    line: int | None
    column: int | None
    message_key: ImportParserIssueMessageKey


@dataclass(frozen=True, slots=True)
class ImportJobRecord:
    """Closed public projection of one published mapping and its logical import."""

    id: UUID | None
    mapping_id: UUID
    active_revision_id: UUID
    topology: Literal["direct", "separate"]
    repository_sides: tuple[ImportRepositorySideRecord, ...]
    state: ImportState
    dataset_status: ImportDatasetStatusRecord
    parser_issues: tuple[ImportParserIssueRecord, ...]
    parser_issue_remaining_count: int
    active_baseline: ImportBaselineRecord | None
    execution_number: int | None
    latest_execution_at: datetime | None
    retry_count: int
    capability: ImportCapability
    error_category: ImportErrorCategory | None
    error_message: str | None
    action: ImportAction


@dataclass(frozen=True, slots=True)
class ImportJobPage:
    """One bounded page tied to an immutable active revision and filter."""

    items: tuple[ImportJobRecord, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class _ImportCursor:
    product_id: UUID
    revision_id: UUID
    status_filter: ImportStatusFilter
    order: Literal["mapping_identity_v1"]
    identity_key: str
    mapping_id: UUID


@dataclass(frozen=True, slots=True)
class ImportRewriteSideRecord:
    """One exact metadata-only side of a current rewrite proposal."""

    repository_side: RepositoryRole
    repository_id: UUID
    old_commit_hash: str
    new_commit_hash: str
    added_count: int
    modified_count: int
    removed_count: int


@dataclass(frozen=True, slots=True)
class ImportRewriteDeltaRecord:
    """One bounded ordered localization-file delta row."""

    position: int
    repository_side: RepositoryRole
    change: RewriteDeltaChange
    path: str


@dataclass(frozen=True, slots=True)
class ImportRewriteComparisonRecord:
    """Complete current confirmation authority exposed without provider data."""

    proposal_id: UUID
    import_id: UUID
    mapping_id: UUID
    proposed_execution_id: UUID
    proposal_digest: str
    topology: Literal["direct", "separate"]
    confirmable: Literal[True]
    sides: tuple[ImportRewriteSideRecord, ...]
    files: tuple[ImportRewriteDeltaRecord, ...]


@dataclass(frozen=True, slots=True)
class ImportExecutionSide:
    role: RepositoryRole
    repository_id: UUID
    workspace: str
    repository_slug: str
    source_branch: str
    localization_root: str | None = None


@dataclass(frozen=True, slots=True)
class ImportExecutionIdentity:
    import_id: UUID
    execution_id: UUID
    sequence: int
    product_id: UUID
    revision_id: UUID
    mapping_id: UUID
    connection_generation: int
    repository_sides: tuple[ImportExecutionSide, ...]


@dataclass(frozen=True, slots=True)
class SourceMovementInput:
    """Exact active/proposed identity for one side of a published mapping."""

    repository_side: RepositoryRole
    repository_id: UUID
    workspace: str
    repository_slug: str
    active_commit_hash: str
    proposed_commit_hash: str


@dataclass(frozen=True, slots=True)
class SourceMovementSideComparison:
    """Provider-independent, metadata-only comparison for one mapping side."""

    repository_side: RepositoryRole
    repository_id: UUID
    active_commit_hash: str
    proposed_commit_hash: str
    relation: SourceMovementRelation


@dataclass(frozen=True, slots=True)
class SourceRewriteCandidate:
    """Complete mapping-scoped rewrite evidence, ready for later persistence."""

    sides: tuple[SourceMovementSideComparison, ...]
    files: tuple[BitbucketFileDelta, ...]
    complete: bool


@dataclass(frozen=True, slots=True)
class SourceMovementClassification:
    """Closed classification of movement for exactly one mapping."""

    movement: SourceMovementKind
    sides: tuple[SourceMovementSideComparison, ...]
    rewrite_candidate: SourceRewriteCandidate | None


@dataclass(frozen=True, slots=True)
class ImportProcessingResult:
    """Provider-read result plus optional complete rewrite authority."""

    references: tuple[ImportSourceReferenceRecord, ...]
    movement: SourceMovementClassification | None = None
    canonical_manifest_digest: str | None = None


ImportProcessor = Callable[
    [ImportExecutionIdentity],
    tuple[ImportSourceReferenceRecord, ...] | ImportProcessingResult,
]
ImportClock = Callable[[], datetime]


_PUBLIC_FAILURE_MESSAGES: dict[ImportErrorCategory, str] = {
    "connection_required": (
        "The organizational Bitbucket connection is not ready for imports. "
        "An administrator must reconnect it before retrying this mapping."
    ),
    "permission_denied": (
        "Bitbucket denied access to this repository or branch. Review the organizational "
        "connection and repository permissions, then retry from this mapping."
    ),
    "rate_limited": (
        "Bitbucket is temporarily limiting requests. Wait a few minutes, then retry this "
        "import from the mapping."
    ),
    "source_not_found": (
        "The configured repository, branch, or localization file could not be found. "
        "Review the mapping configuration before retrying."
    ),
    "timeout": (
        "Bitbucket did not respond within the safe time limit. {baseline_sentence} Retry later."
    ),
    "provider_unavailable": (
        "Bitbucket could not complete this import. {baseline_sentence} Retry later."
    ),
    "bounded_failure": (
        "The source could not be read within the safe import limits. {baseline_sentence} "
        "Review the mapping before retrying."
    ),
}

_PROVIDER_FAILURE_CATEGORIES: dict[str, ImportErrorCategory] = {
    "disconnected": "connection_required",
    "reauthorization_required": "connection_required",
    "permission_denied": "permission_denied",
    "rate_limited": "rate_limited",
    "not_found": "source_not_found",
    "timeout": "timeout",
    "unavailable": "provider_unavailable",
    "invalid_source": "bounded_failure",
    "limit_exceeded": "bounded_failure",
}


def _public_failure_message(
    category: ImportErrorCategory,
    *,
    has_baseline: bool,
) -> str:
    baseline_sentence = (
        "The last successful baseline is unchanged."
        if has_baseline
        else "No import baseline was created."
    )
    return _PUBLIC_FAILURE_MESSAGES[category].format(
        baseline_sentence=baseline_sentence,
    )


def _provider_failure_category(kind: str) -> ImportErrorCategory:
    return _PROVIDER_FAILURE_CATEGORIES.get(kind, "provider_unavailable")


def _encode_import_cursor(position: _ImportCursor) -> str:
    payload = json.dumps(
        {
            "f": position.status_filter,
            "i": str(position.mapping_id),
            "k": position.identity_key,
            "o": position.order,
            "p": str(position.product_id),
            "r": str(position.revision_id),
            "v": _IMPORT_CURSOR_VERSION,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_import_cursor(
    cursor: str,
    *,
    product_id: UUID,
    revision_id: UUID,
    status_filter: ImportStatusFilter,
) -> _ImportCursor:
    if not isinstance(cursor, str) or not cursor or len(cursor) > MAX_IMPORT_CURSOR_LENGTH:
        raise InvalidImportCursor("invalid import cursor")
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or set(payload) != {"f", "i", "k", "o", "p", "r", "v"}:
            raise ValueError
        position = _ImportCursor(
            product_id=UUID(payload["p"]),
            revision_id=UUID(payload["r"]),
            status_filter=cast(ImportStatusFilter, payload["f"]),
            order=cast(Literal["mapping_identity_v1"], payload["o"]),
            identity_key=payload["k"],
            mapping_id=UUID(payload["i"]),
        )
        if (
            payload["v"] != _IMPORT_CURSOR_VERSION
            or position.product_id != product_id
            or position.revision_id != revision_id
            or position.status_filter != status_filter
            or position.status_filter not in {"all", "attention"}
            or position.order != _IMPORT_ORDER_IDENTITY
            or not isinstance(position.identity_key, str)
            or not position.identity_key
            or len(position.identity_key) > 1024
            or position.mapping_id.int == 0
            or _encode_import_cursor(position) != cursor
        ):
            raise ValueError
    except (
        AttributeError,
        ValueError,
        TypeError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as error:
        raise InvalidImportCursor("invalid import cursor") from error
    return position


def _reject_source_movement(*, operation: BitbucketOperation) -> NoReturn:
    raise BitbucketProviderReadError(
        kind="invalid_source",
        operation=operation,
    )


def _validated_source_movement_inputs(
    sources: tuple[SourceMovementInput, ...],
) -> tuple[SourceMovementInput, ...]:
    roles = tuple(source.repository_side for source in sources)
    if roles not in {("direct",), ("keys", "translations")}:
        _reject_source_movement(operation=BitbucketOperation.COMMIT_ANCESTRY)
    for source in sources:
        if (
            not isinstance(source.repository_id, UUID)
            or source.repository_id.int == 0
            or not isinstance(source.workspace, str)
            or not isinstance(source.repository_slug, str)
        ):
            _reject_source_movement(operation=BitbucketOperation.COMMIT_ANCESTRY)
        try:
            repository_metadata_url(
                workspace=source.workspace,
                repository_slug=source.repository_slug,
            )
            validate_provider_commit_hash(source.active_commit_hash)
            validate_provider_commit_hash(source.proposed_commit_hash)
        except ValueError:
            _reject_source_movement(operation=BitbucketOperation.COMMIT_ANCESTRY)
    return sources


def _validated_side_delta(
    source: SourceMovementInput,
    delta: BitbucketCommitDelta,
) -> tuple[BitbucketFileDelta, ...]:
    if (
        delta.complete is not True
        or delta.old_commit_hash != source.active_commit_hash
        or delta.new_commit_hash != source.proposed_commit_hash
        or tuple(file.ordinal for file in delta.files) != tuple(range(len(delta.files)))
    ):
        _reject_source_movement(operation=BitbucketOperation.COMMIT_DIFFSTAT)
    seen_paths: set[str] = set()
    for file in delta.files:
        try:
            path = validate_repository_relative_path(file.path)
        except ValueError:
            _reject_source_movement(operation=BitbucketOperation.COMMIT_DIFFSTAT)
        if (
            file.repository_side != source.repository_side
            or file.change not in {"added", "modified", "removed"}
            or path != file.path
            or not path.casefold().endswith((".xml", ".ts", ".json", ".strings"))
            or path in seen_paths
        ):
            _reject_source_movement(operation=BitbucketOperation.COMMIT_DIFFSTAT)
        seen_paths.add(path)
    return delta.files


async def classify_source_movement(
    session: Session,
    *,
    sources: tuple[SourceMovementInput, ...],
    adapter: SourceDiscoveryAdapter,
) -> SourceMovementClassification:
    """Classify one direct or atomic separate mapping from exact fresh commits."""
    validated_sources = _validated_source_movement_inputs(sources)
    comparisons: list[SourceMovementSideComparison] = []
    for source in validated_sources:
        if source.active_commit_hash == source.proposed_commit_hash:
            relation: SourceMovementRelation = "equal"
        else:
            ancestry = await adapter.compare_repository_ancestry(
                session,
                workspace=source.workspace,
                repository_slug=source.repository_slug,
                old_commit_hash=source.active_commit_hash,
                new_commit_hash=source.proposed_commit_hash,
            )
            if (
                ancestry.complete is not True
                or ancestry.old_commit_hash != source.active_commit_hash
                or ancestry.new_commit_hash != source.proposed_commit_hash
                or ancestry.relation not in {"equal", "descendant", "diverged"}
                or ancestry.relation == "equal"
            ):
                _reject_source_movement(operation=BitbucketOperation.COMMIT_ANCESTRY)
            relation = ancestry.relation
        comparisons.append(
            SourceMovementSideComparison(
                repository_side=source.repository_side,
                repository_id=source.repository_id,
                active_commit_hash=source.active_commit_hash,
                proposed_commit_hash=source.proposed_commit_hash,
                relation=relation,
            )
        )

    comparison_tuple = tuple(comparisons)
    if all(comparison.relation == "equal" for comparison in comparison_tuple):
        return SourceMovementClassification(
            movement="equal",
            sides=comparison_tuple,
            rewrite_candidate=None,
        )
    if all(comparison.relation in {"equal", "descendant"} for comparison in comparison_tuple):
        return SourceMovementClassification(
            movement="fast-forward",
            sides=comparison_tuple,
            rewrite_candidate=None,
        )

    files: list[BitbucketFileDelta] = []
    for source, comparison in zip(validated_sources, comparison_tuple, strict=True):
        if comparison.relation == "equal":
            continue
        delta = await adapter.list_repository_diffstat(
            session,
            workspace=source.workspace,
            repository_slug=source.repository_slug,
            old_commit_hash=source.active_commit_hash,
            new_commit_hash=source.proposed_commit_hash,
            repository_side=source.repository_side,
        )
        files.extend(_validated_side_delta(source, delta))
    candidate = SourceRewriteCandidate(
        sides=comparison_tuple,
        files=tuple(files),
        complete=True,
    )
    return SourceMovementClassification(
        movement="review-required",
        sides=comparison_tuple,
        rewrite_candidate=candidate,
    )


def _connected_generation(session: Session) -> int:
    connection = session.execute(
        select(BitbucketConnection).where(BitbucketConnection.id == 1).with_for_update()
    ).scalar_one_or_none()
    if (
        connection is None
        or connection.access_token_ciphertext is None
        or connection.refresh_token_ciphertext is not None
        or connection.scope_profile != PULLREQUEST_WRITE_SCOPE
        or connection.provider_expires_at is None
        or connection.provider_expires_at <= datetime.now(UTC)
        or connection.revoked_at is not None
    ):
        raise ImportConnectionUnavailable("import connection unavailable")
    return connection.generation


def _published_mapping_statement(
    *, product_id: UUID, mapping_id: UUID | None = None
) -> Select[tuple[ProductRepositoryMapping]]:
    statement = (
        select(ProductRepositoryMapping)
        .options(selectinload(ProductRepositoryMapping.sides))
        .join(
            ProductRevision,
            ProductRevision.id == ProductRepositoryMapping.revision_id,
        )
        .join(
            Product,
            (Product.id == product_id) & (Product.active_revision_id == ProductRevision.id),
        )
        .where(
            Product.is_active.is_(True),
            Product.deleted_at.is_(None),
            ProductRevision.product_id == product_id,
            ProductRevision.is_published.is_(True),
            ProductRepositoryMapping.topology.in_(("direct", "separate")),
        )
    )
    if mapping_id is not None:
        statement = statement.where(ProductRepositoryMapping.id == mapping_id)
    return statement.order_by(ProductRepositoryMapping.id)


def _mapping_sides(
    mapping: ProductRepositoryMapping,
) -> tuple[ImportRepositorySideRecord, ...]:
    sides = tuple(
        ImportRepositorySideRecord(
            role=cast(RepositoryRole, side.role),
            repository_id=side.repository_id,
            source_branch=side.source_branch,
            localization_root=side.localization_root,
        )
        for side in mapping.sides
    )
    expected_roles = {
        "direct": ("direct",),
        "separate": ("keys", "translations"),
    }.get(mapping.topology)
    if expected_roles is None or tuple(side.role for side in sides) != expected_roles:
        raise ImportConflict("published import mapping rejected")
    return sides


def _locked_published_mapping(
    session: Session,
    *,
    product_id: UUID,
    mapping_id: UUID,
) -> tuple[ProductRevision, ProductRepositoryMapping]:
    product = session.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    ).scalar_one_or_none()
    if (
        product is None
        or product.deleted_at is not None
        or not product.is_active
        or product.active_revision_id is None
    ):
        raise ImportNotFound("published import unavailable")
    revision = session.execute(
        select(ProductRevision)
        .where(
            ProductRevision.id == product.active_revision_id,
            ProductRevision.product_id == product_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if revision is None or not revision.is_published:
        raise ImportNotFound("published import unavailable")
    mapping = session.execute(
        select(ProductRepositoryMapping)
        .options(selectinload(ProductRepositoryMapping.sides))
        .where(
            ProductRepositoryMapping.id == mapping_id,
            ProductRepositoryMapping.revision_id == revision.id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if mapping is None:
        raise ImportNotFound("published import unavailable")
    _mapping_sides(mapping)
    return revision, mapping


def _source_references(
    session: Session,
    *,
    execution_id: UUID,
) -> tuple[ImportSourceReferenceRecord, ...]:
    rows = session.execute(
        select(ImportSourceReference)
        .where(ImportSourceReference.execution_id == execution_id)
        .order_by(ImportSourceReference.position)
    ).scalars()
    return tuple(
        ImportSourceReferenceRecord(
            position=row.position,
            repository_side=cast(RepositoryRole, row.repository_side),
            repository_id=row.repository_id,
            source_branch=row.source_branch,
            commit_hash=row.commit_hash,
            path=row.path,
            size_bytes=row.size_bytes,
            sha256=row.sha256,
        )
        for row in rows
    )


def _current_import_capability(session: Session) -> ImportCapability:
    connection = session.get(BitbucketConnection, 1)
    if connection is None or connection.revoked_at is not None:
        return "unavailable"
    if (
        connection.access_token_ciphertext is not None
        and connection.refresh_token_ciphertext is None
        and connection.scope_profile == PULLREQUEST_WRITE_SCOPE
        and connection.provider_expires_at is not None
        and connection.provider_expires_at > datetime.now(UTC)
    ):
        return "ready"
    if connection.access_token_ciphertext is not None:
        return "reauthorization_required"
    return "unavailable"


def _pending_rewrite_mapping_ids(
    session: Session,
    *,
    import_ids: tuple[UUID, ...],
) -> frozenset[UUID]:
    if not import_ids:
        return frozenset()
    return frozenset(
        session.scalars(
            select(ImportRewriteProposal.mapping_id).where(
                ImportRewriteProposal.import_job_id.in_(import_ids),
                ImportRewriteProposal.status == "pending",
                ImportRewriteProposal.complete.is_(True),
            )
        )
    )


def _record(
    session: Session,
    *,
    product_id: UUID,
    mapping: ProductRepositoryMapping,
    job: ImportJob | None,
    capability: ImportCapability,
    review_required: bool = False,
) -> ImportJobRecord:
    sides = _mapping_sides(mapping)
    scope = session.execute(
        select(LocalizationScope)
        .where(
            LocalizationScope.product_id == product_id,
            LocalizationScope.mapping_identity_key == mapping.identity_key,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if job is None:
        dataset_status: ImportDatasetStatusRecord = (
            "retained"
            if scope is not None and scope.active_execution_id is not None
            else "not_created"
        )
        return ImportJobRecord(
            id=None,
            mapping_id=mapping.id,
            active_revision_id=mapping.revision_id,
            topology=cast(Literal["direct", "separate"], mapping.topology),
            repository_sides=sides,
            state="not_imported",
            dataset_status=dataset_status,
            parser_issues=(),
            parser_issue_remaining_count=0,
            active_baseline=None,
            execution_number=None,
            latest_execution_at=None,
            retry_count=0,
            capability=capability,
            error_category=None,
            error_message=None,
            action="run_import",
        )
    if job.state not in {"queued", "running", "current", "import_failed"}:
        raise ImportConflict("persisted import state rejected")
    baseline: ImportBaselineRecord | None = None
    if job.active_baseline_execution_id is not None:
        baseline_execution = session.get(
            ImportExecution,
            job.active_baseline_execution_id,
        )
        if (
            baseline_execution is None
            or baseline_execution.import_job_id != job.id
            or baseline_execution.state != "succeeded"
            or baseline_execution.finished_at is None
        ):
            raise ImportConflict("persisted import baseline rejected")
        baseline = ImportBaselineRecord(
            imported_at=baseline_execution.finished_at,
            source_references=_source_references(
                session,
                execution_id=baseline_execution.id,
            ),
        )
    current_execution = session.execute(
        select(ImportExecution).where(
            ImportExecution.id == job.current_execution_id,
            ImportExecution.import_job_id == job.id,
        )
    ).scalar_one_or_none()
    if current_execution is None:
        raise ImportConflict("persisted import execution rejected")
    dataset_status = _dataset_status(
        scope=scope,
        job=job,
        current_execution=current_execution,
    )
    parser_issues, parser_issue_remaining_count = _parser_issue_projection(
        session,
        job=job,
        current_execution=current_execution,
        expected_sides=sides,
    )
    public_state: ImportState
    action: ImportAction
    if review_required:
        public_state = "review_required"
        action = "review_baseline_change"
    elif job.state == "import_failed" and baseline is not None:
        public_state = "may_be_stale"
        action = "retry_import"
    elif job.state == "import_failed":
        public_state = "import_failed"
        action = "retry_import"
    elif job.state in {"queued", "running"}:
        public_state = cast(ImportState, job.state)
        action = "import_in_progress"
    else:
        public_state = "current"
        action = "refresh_import"
    if job.error_category is not None and job.error_category not in {
        "connection_required",
        "permission_denied",
        "rate_limited",
        "source_not_found",
        "timeout",
        "provider_unavailable",
        "bounded_failure",
    }:
        raise ImportConflict("persisted import error rejected")
    return ImportJobRecord(
        id=job.id,
        mapping_id=job.mapping_id,
        active_revision_id=job.revision_id,
        topology=cast(Literal["direct", "separate"], job.topology),
        repository_sides=sides,
        state=public_state,
        dataset_status=dataset_status,
        parser_issues=parser_issues,
        parser_issue_remaining_count=parser_issue_remaining_count,
        active_baseline=baseline,
        execution_number=current_execution.sequence,
        latest_execution_at=job.latest_execution_at,
        retry_count=job.retry_count,
        capability=capability,
        error_category=cast(
            ImportErrorCategory | None,
            job.error_category,
        ),
        error_message=job.error_message,
        action=action,
    )


def _dataset_status(
    *,
    scope: LocalizationScope | None,
    job: ImportJob,
    current_execution: ImportExecution,
) -> ImportDatasetStatusRecord:
    """Project only durable canonical dataset authority, never request state."""
    if scope is None or scope.active_execution_id is None:
        return "not_created"
    if scope.active_execution_id != current_execution.id:
        return "retained"
    if (
        job.state != "current"
        or current_execution.state != "succeeded"
        or scope.active_import_job_id != job.id
    ):
        raise ImportConflict("persisted active dataset rejected")
    return "active"


def _parser_issue_projection(
    session: Session,
    *,
    job: ImportJob,
    current_execution: ImportExecution,
    expected_sides: tuple[ImportRepositorySideRecord, ...],
) -> tuple[tuple[ImportParserIssueRecord, ...], int]:
    """Return current failed-execution issues without stored diagnostic prose."""
    if job.state != "import_failed" or current_execution.state != "failed":
        return (), 0
    rows = tuple(
        session.scalars(
            select(TranslationParseIssue).where(
                TranslationParseIssue.import_execution_id == current_execution.id,
                TranslationParseIssue.import_job_id == job.id,
            )
        )
    )
    if len(rows) > MAX_PUBLIC_PARSER_ISSUE_TOTAL:
        raise ImportConflict("persisted parser issues rejected")
    allowed_sides = {side.role for side in expected_sides}
    records: list[tuple[int, int, ImportParserIssueRecord]] = []
    for row in rows:
        code = cast(ImportParserIssueCode, row.issue_code)
        side = cast(RepositoryRole, row.repository_side)
        try:
            path = validate_repository_relative_path(row.path)
            message_key = _PARSER_ISSUE_MESSAGE_KEYS[code]
            side_order = _PARSER_ISSUE_SIDE_ORDER[side]
        except (KeyError, ValueError) as error:
            raise ImportConflict("persisted parser issues rejected") from error
        if (
            side not in allowed_sides
            or path != row.path
            or not 1 <= len(path) <= 4096
            or row.position < 0
            or row.line is not None
            and not 1 <= row.line <= 2_147_483_647
            or row.column is not None
            and not 1 <= row.column <= 2_147_483_647
        ):
            raise ImportConflict("persisted parser issues rejected")
        records.append(
            (
                side_order,
                row.position,
                ImportParserIssueRecord(
                    issue_code=code,
                    repository_side=side,
                    path=path,
                    line=row.line,
                    column=row.column,
                    message_key=message_key,
                ),
            )
        )
    ordered = tuple(
        record
        for _side, _position, record in sorted(
            records,
            key=lambda item: (item[0], item[1]),
        )
    )
    return (
        ordered[:MAX_PUBLIC_PARSER_ISSUES],
        len(ordered) - min(len(ordered), MAX_PUBLIC_PARSER_ISSUES),
    )


def list_published_mapping_imports(
    session: Session,
    *,
    product_id: UUID,
    limit: int = DEFAULT_IMPORT_PAGE_SIZE,
    cursor: str | None = None,
    status_filter: ImportStatusFilter = "all",
) -> ImportJobPage:
    """List a bounded active-revision page in canonical mapping identity order."""
    if not 1 <= limit <= MAX_IMPORT_PAGE_SIZE or status_filter not in {"all", "attention"}:
        raise ValueError("invalid import collection input")
    with session.begin():
        # Activation/publication take this first lock exclusively. Retain one
        # read snapshot across jobs and eager mapping scopes in READ COMMITTED.
        product = session.execute(
            select(Product).where(Product.id == product_id).with_for_update(read=True)
        ).scalar_one_or_none()
        if (
            product is None
            or product.deleted_at is not None
            or not product.is_active
            or product.active_revision_id is None
        ):
            raise ImportNotFound("published imports unavailable")
        revision_id = product.active_revision_id
        position = (
            _decode_import_cursor(
                cursor,
                product_id=product_id,
                revision_id=revision_id,
                status_filter=status_filter,
            )
            if cursor is not None
            else None
        )
        statement = _published_mapping_statement(product_id=product_id).order_by(None)
        if status_filter == "attention":
            pending_proposal = exists(
                select(ImportRewriteProposal.id)
                .join(ImportJob, ImportJob.id == ImportRewriteProposal.import_job_id)
                .where(
                    ImportJob.mapping_id == ProductRepositoryMapping.id,
                    ImportRewriteProposal.status == "pending",
                    ImportRewriteProposal.complete.is_(True),
                )
            )
            failed_import = exists(
                select(ImportJob.id).where(
                    ImportJob.mapping_id == ProductRepositoryMapping.id,
                    ImportJob.revision_id == revision_id,
                    ImportJob.state == "import_failed",
                )
            )
            statement = statement.where(or_(pending_proposal, failed_import))
        if position is not None:
            statement = statement.where(
                or_(
                    ProductRepositoryMapping.identity_key > position.identity_key,
                    and_(
                        ProductRepositoryMapping.identity_key == position.identity_key,
                        ProductRepositoryMapping.id > position.mapping_id,
                    ),
                )
            )
        mappings = tuple(
            session.execute(
                statement.order_by(
                    ProductRepositoryMapping.identity_key,
                    ProductRepositoryMapping.id,
                ).limit(limit + 1)
            ).scalars()
        )
        page_mappings = mappings[:limit]
        jobs = {
            job.mapping_id: job
            for job in session.execute(
                select(ImportJob).where(
                    ImportJob.revision_id == revision_id,
                    ImportJob.mapping_id.in_(tuple(mapping.id for mapping in page_mappings)),
                )
            ).scalars()
        }
        pending_mapping_ids = _pending_rewrite_mapping_ids(
            session,
            import_ids=tuple(job.id for job in jobs.values()),
        )
        capability = _current_import_capability(session)
        items = tuple(
            _record(
                session,
                product_id=product_id,
                mapping=mapping,
                job=jobs.get(mapping.id),
                capability=capability,
                review_required=mapping.id in pending_mapping_ids,
            )
            for mapping in page_mappings
        )
        next_cursor = (
            _encode_import_cursor(
                _ImportCursor(
                    product_id=product_id,
                    revision_id=revision_id,
                    status_filter=status_filter,
                    order="mapping_identity_v1",
                    identity_key=page_mappings[-1].identity_key,
                    mapping_id=page_mappings[-1].id,
                )
            )
            if len(mappings) > limit and page_mappings
            else None
        )
        return ImportJobPage(items=items, next_cursor=next_cursor)


def enqueue_import_job(import_id: UUID) -> None:
    """Dispatch one JSON task carrying only the stable logical import UUID."""
    from verboflex.worker.celery_app import app

    settings = get_settings()
    app.send_task(
        IMPORT_TASK_NAME,
        args=[str(import_id)],
        task_id=str(import_id),
        serializer="json",
        soft_time_limit=settings.import_soft_time_limit_seconds,
        time_limit=settings.import_hard_time_limit_seconds,
    )


def start_or_refresh_import(
    session: Session,
    *,
    product_id: UUID,
    mapping_id: UUID,
    enqueuer: ImportEnqueuer = enqueue_import_job,
) -> ImportJobRecord:
    """Commit one queued logical UUID before dispatching that UUID only."""
    should_enqueue = False
    with session.begin():
        revision, mapping = _locked_published_mapping(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
        )
        connection_generation = _connected_generation(session)
        job = session.execute(
            select(ImportJob).where(ImportJob.mapping_id == mapping.id).with_for_update()
        ).scalar_one_or_none()
        if job is not None:
            pending_proposal = session.scalar(
                select(ImportRewriteProposal.id).where(
                    ImportRewriteProposal.import_job_id == job.id,
                    ImportRewriteProposal.mapping_id == mapping.id,
                    ImportRewriteProposal.status == "pending",
                    ImportRewriteProposal.complete.is_(True),
                )
            )
            if pending_proposal is not None:
                raise ImportReviewRequired("published import requires review")
        if job is None:
            now = datetime.now(UTC)
            job_id = uuid4()
            execution_id = uuid4()
            job = ImportJob(
                id=job_id,
                product_id=product_id,
                revision_id=revision.id,
                mapping_id=mapping.id,
                topology=mapping.topology,
                state="queued",
                current_execution_id=execution_id,
                active_baseline_execution_id=None,
                retry_count=0,
                latest_execution_at=now,
            )
            execution = ImportExecution(
                id=execution_id,
                import_job_id=job_id,
                sequence=1,
                state="queued",
                connection_generation=connection_generation,
            )
            # SQLAlchemy cannot infer the insert order from UUID columns alone.
            # Persist the logical job first; its execution pointer is deferred at
            # the database boundary until the execution is inserted below.
            session.add(job)
            session.flush()
            session.add(execution)
            session.flush()
            should_enqueue = True
        elif job.state in {"current", "import_failed"}:
            now = datetime.now(UTC)
            current_execution = session.execute(
                select(ImportExecution)
                .where(
                    ImportExecution.id == job.current_execution_id,
                    ImportExecution.import_job_id == job.id,
                )
                .with_for_update()
            ).scalar_one_or_none()
            if current_execution is None:
                raise ImportConflict("persisted import execution rejected")
            expected_terminal_state = "succeeded" if job.state == "current" else "failed"
            if current_execution.state != expected_terminal_state:
                raise ImportConflict("persisted import execution rejected")
            execution = ImportExecution(
                id=uuid4(),
                import_job_id=job.id,
                sequence=current_execution.sequence + 1,
                state="queued",
                connection_generation=connection_generation,
            )
            session.add(execution)
            job.current_execution_id = execution.id
            job.state = "queued"
            if current_execution.state == "failed":
                job.retry_count += 1
            job.error_category = None
            job.error_message = None
            job.latest_execution_at = now
            job.updated_at = now
            session.flush()
            should_enqueue = True
        elif job.state in {"queued", "running"}:
            raise ImportAlreadyInProgress("published import already in progress")
        else:
            raise ImportConflict("persisted import state rejected")
        record = _record(
            session,
            product_id=product_id,
            mapping=mapping,
            job=job,
            capability="ready",
        )

    if not should_enqueue:
        return record
    assert record.id is not None
    try:
        enqueuer(record.id)
    except Exception:
        with session.begin():
            job = session.execute(
                select(ImportJob).where(ImportJob.id == record.id).with_for_update()
            ).scalar_one()
            execution = session.execute(
                select(ImportExecution)
                .where(
                    ImportExecution.id == job.current_execution_id,
                    ImportExecution.import_job_id == job.id,
                )
                .with_for_update()
            ).scalar_one()
            if job.state == "queued" and execution.state == "queued":
                now = datetime.now(UTC)
                execution.state = "failed"
                execution.started_at = now
                execution.finished_at = now
                job.state = "import_failed"
                job.error_category = "provider_unavailable"
                job.error_message = _public_failure_message(
                    "provider_unavailable",
                    has_baseline=job.active_baseline_execution_id is not None,
                )
                job.updated_at = now
            mapping = session.execute(
                select(ProductRepositoryMapping)
                .options(selectinload(ProductRepositoryMapping.sides))
                .where(ProductRepositoryMapping.id == job.mapping_id)
            ).scalar_one()
            record = _record(
                session,
                product_id=product_id,
                mapping=mapping,
                job=job,
                capability=_current_import_capability(session),
            )
    return record


# Compatibility name retained for existing callers while the route adopts the
# stable Phase 3 state-machine vocabulary.
create_or_start_import = start_or_refresh_import


def get_import_job(
    session: Session,
    *,
    product_id: UUID,
    import_id: UUID,
) -> ImportJobRecord:
    """Read PostgreSQL-authoritative import state without consulting Celery."""
    with session.begin():
        # Match the worker's first authority lock before loading either the job
        # or its scope; otherwise identity-map values can span activation commits.
        product = session.execute(
            select(Product).where(Product.id == product_id).with_for_update(read=True)
        ).scalar_one_or_none()
        job = session.get(ImportJob, import_id)
        if (
            product is None
            or product.deleted_at is not None
            or not product.is_active
            or product.active_revision_id is None
            or job is None
            or job.product_id != product_id
            or job.revision_id != product.active_revision_id
        ):
            raise ImportNotFound("import unavailable")
        mapping = session.execute(
            _published_mapping_statement(
                product_id=product_id,
                mapping_id=job.mapping_id,
            )
        ).scalar_one_or_none()
        if mapping is None:
            raise ImportNotFound("import unavailable")
        review_required = (
            session.scalar(
                select(ImportRewriteProposal.id).where(
                    ImportRewriteProposal.import_job_id == job.id,
                    ImportRewriteProposal.mapping_id == mapping.id,
                    ImportRewriteProposal.status == "pending",
                    ImportRewriteProposal.complete.is_(True),
                )
            )
            is not None
        )
        return _record(
            session,
            product_id=product_id,
            mapping=mapping,
            job=job,
            capability=_current_import_capability(session),
            review_required=review_required,
        )


def start_import_execution(
    factory: sessionmaker[Session],
    *,
    import_id: UUID,
) -> ImportExecutionIdentity | None:
    """Claim one queued execution under the canonical authority lock order."""
    with factory.begin() as session:
        snapshot = session.get(ImportJob, import_id)
        if snapshot is None:
            return None
        product_id = snapshot.product_id
        revision_id = snapshot.revision_id
        mapping_id = snapshot.mapping_id
        current_execution_id = snapshot.current_execution_id

        product = session.execute(
            select(Product).where(Product.id == product_id).with_for_update()
        ).scalar_one_or_none()
        revision = session.execute(
            select(ProductRevision)
            .where(
                ProductRevision.id == revision_id,
                ProductRevision.product_id == product_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        mapping = session.execute(
            select(ProductRepositoryMapping)
            .options(selectinload(ProductRepositoryMapping.sides))
            .where(
                ProductRepositoryMapping.id == mapping_id,
                ProductRepositoryMapping.revision_id == revision_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        try:
            connection_generation = _connected_generation(session)
        except ImportConnectionUnavailable:
            connection_generation = None
        job = session.execute(
            select(ImportJob).where(ImportJob.id == import_id).with_for_update()
        ).scalar_one_or_none()
        if job is None or job.state != "queued":
            return None
        execution = session.execute(
            select(ImportExecution)
            .where(
                ImportExecution.id == current_execution_id,
                ImportExecution.import_job_id == import_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        authority_is_current = (
            product is not None
            and product.is_active
            and product.active_revision_id == revision_id
            and revision is not None
            and revision.is_published
            and mapping is not None
            and job.product_id == product_id
            and job.revision_id == revision_id
            and job.mapping_id == mapping_id
            and job.topology == mapping.topology
            and job.current_execution_id == current_execution_id
            and execution is not None
            and execution.state == "queued"
            and connection_generation == execution.connection_generation
        )
        execution_sides: list[ImportExecutionSide] = []
        if authority_is_current:
            assert mapping is not None
            try:
                sides = _mapping_sides(mapping)
            except ImportConflict:
                authority_is_current = False
            else:
                for side in sides:
                    repository = session.get(Repository, side.repository_id)
                    if repository is None:
                        authority_is_current = False
                        break
                    execution_sides.append(
                        ImportExecutionSide(
                            role=side.role,
                            repository_id=side.repository_id,
                            workspace=repository.workspace,
                            repository_slug=repository.repository_slug,
                            source_branch=side.source_branch,
                            localization_root=side.localization_root,
                        )
                    )
        now = datetime.now(UTC)
        if not authority_is_current:
            if execution is not None and execution.state == "queued":
                execution.state = "failed"
                execution.started_at = now
                execution.finished_at = now
            job.state = "import_failed"
            failure_category: ImportErrorCategory = (
                "connection_required"
                if execution is not None
                and connection_generation != execution.connection_generation
                else "bounded_failure"
            )
            job.error_category = failure_category
            job.error_message = _public_failure_message(
                failure_category,
                has_baseline=job.active_baseline_execution_id is not None,
            )
            job.updated_at = now
            return None
        assert execution is not None
        execution.state = "running"
        execution.started_at = now
        job.state = "running"
        job.updated_at = now
        return ImportExecutionIdentity(
            import_id=job.id,
            execution_id=execution.id,
            sequence=execution.sequence,
            product_id=job.product_id,
            revision_id=job.revision_id,
            mapping_id=job.mapping_id,
            connection_generation=execution.connection_generation,
            repository_sides=tuple(execution_sides),
        )


def _validated_references(
    identity: ImportExecutionIdentity,
    references: tuple[ImportSourceReferenceRecord, ...],
) -> tuple[ImportSourceReferenceRecord, ...]:
    if not references:
        raise ValueError("import references rejected")
    expected_sides = tuple(
        (side.role, side.repository_id, side.source_branch) for side in identity.repository_sides
    )
    expected_side_set = set(expected_sides)
    if tuple(reference.position for reference in references) != tuple(range(len(references))):
        raise ValueError("import references rejected")
    role_order = {side[0]: position for position, side in enumerate(expected_sides)}
    reference_roles = tuple(reference.repository_side for reference in references)
    if set(reference_roles) != set(role_order) or tuple(
        role_order[role] for role in reference_roles
    ) != tuple(sorted(role_order[role] for role in reference_roles)):
        raise ValueError("import references rejected")
    seen_side_paths: set[tuple[RepositoryRole, str]] = set()
    for reference in references:
        side_path = (reference.repository_side, reference.path)
        if (
            (
                reference.repository_side,
                reference.repository_id,
                reference.source_branch,
            )
            not in expected_side_set
            or len(reference.commit_hash) != 40
            or any(character not in "0123456789abcdef" for character in reference.commit_hash)
            or not reference.path
            or reference.size_bytes < 0
            or len(reference.sha256) != 64
            or any(character not in "0123456789abcdef" for character in reference.sha256)
            or side_path in seen_side_paths
        ):
            raise ValueError("import references rejected")
        seen_side_paths.add(side_path)
    return references


def _single_commit_per_side(
    references: tuple[ImportSourceReferenceRecord, ...],
) -> dict[RepositoryRole, tuple[UUID, str]]:
    commits: dict[RepositoryRole, tuple[UUID, str]] = {}
    for reference in references:
        identity = (reference.repository_id, reference.commit_hash)
        existing = commits.setdefault(reference.repository_side, identity)
        if existing != identity:
            raise ValueError("rewrite proposal references rejected")
    return commits


def _rewrite_authority_digest(
    *,
    import_id: UUID,
    product_id: UUID,
    revision_id: UUID,
    revision_version: int,
    mapping_id: UUID,
    topology: str,
    connection_generation: int,
    proposed_execution_id: UUID,
    old_baseline_execution_id: UUID,
    sides: tuple[tuple[RepositoryRole, UUID, str, str], ...],
    files: tuple[tuple[RepositoryRole, int, RewriteDeltaChange, str], ...],
) -> str:
    """Hash every persisted confirmation input in a reconstructible closed shape."""

    digest_payload = {
        "import_id": str(import_id),
        "product_id": str(product_id),
        "revision_id": str(revision_id),
        "revision_version": revision_version,
        "mapping_id": str(mapping_id),
        "topology": topology,
        "connection_generation": connection_generation,
        "proposed_execution_id": str(proposed_execution_id),
        "old_baseline_execution_id": str(old_baseline_execution_id),
        "sides": [
            {
                "repository_side": role,
                "repository_id": str(repository_id),
                "active_commit_hash": old_commit,
                "proposed_commit_hash": new_commit,
            }
            for role, repository_id, old_commit, new_commit in sides
        ],
        "files": [
            {
                "repository_side": role,
                "ordinal": ordinal,
                "change": change,
                "path": path,
            }
            for role, ordinal, change, path in files
        ],
    }
    return hashlib.sha256(
        json.dumps(
            digest_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _validated_rewrite_candidate(
    *,
    identity: ImportExecutionIdentity,
    revision: ProductRevision,
    mapping: ProductRepositoryMapping,
    job: ImportJob,
    references: tuple[ImportSourceReferenceRecord, ...],
    baseline_references: tuple[ImportSourceReferenceRecord, ...],
    movement: SourceMovementClassification,
) -> tuple[SourceRewriteCandidate, str]:
    candidate = movement.rewrite_candidate
    if (
        movement.movement != "review-required"
        or candidate is None
        or candidate.complete is not True
        or candidate.sides != movement.sides
        or job.active_baseline_execution_id is None
    ):
        raise ValueError("rewrite proposal evidence rejected")

    expected_sides = _mapping_sides(mapping)
    expected_roles = tuple(side.role for side in expected_sides)
    if tuple(side.repository_side for side in candidate.sides) != expected_roles:
        raise ValueError("rewrite proposal sides rejected")
    baseline_commits = _single_commit_per_side(baseline_references)
    proposed_commits = _single_commit_per_side(references)
    expected_side_identity = {side.role: side.repository_id for side in expected_sides}
    if set(baseline_commits) != set(expected_roles) or set(proposed_commits) != set(expected_roles):
        raise ValueError("rewrite proposal references rejected")

    diverged = False
    for side in candidate.sides:
        if (
            side.repository_id != expected_side_identity[side.repository_side]
            or baseline_commits[side.repository_side]
            != (side.repository_id, side.active_commit_hash)
            or proposed_commits[side.repository_side]
            != (side.repository_id, side.proposed_commit_hash)
            or side.relation not in {"equal", "descendant", "diverged"}
        ):
            raise ValueError("rewrite proposal identity rejected")
        diverged = diverged or side.relation == "diverged"
    if not diverged:
        raise ValueError("rewrite proposal movement rejected")

    role_positions = {role: position for position, role in enumerate(expected_roles)}
    last_role_position = -1
    side_ordinals: dict[RepositoryRole, int] = {role: 0 for role in expected_roles}
    seen_paths: set[tuple[RepositoryRole, str]] = set()
    for file in candidate.files:
        role = file.repository_side
        if role not in role_positions:
            raise ValueError("rewrite proposal delta rejected")
        try:
            path = validate_repository_relative_path(file.path)
        except ValueError as error:
            raise ValueError("rewrite proposal delta rejected") from error
        if (
            role_positions[role] < last_role_position
            or file.ordinal != side_ordinals[role]
            or file.change not in {"added", "modified", "removed"}
            or path != file.path
            or not path.casefold().endswith((".xml", ".ts", ".json", ".strings"))
            or (role, path) in seen_paths
        ):
            raise ValueError("rewrite proposal delta rejected")
        last_role_position = role_positions[role]
        side_ordinals[role] += 1
        seen_paths.add((role, path))

    digest = _rewrite_authority_digest(
        import_id=identity.import_id,
        product_id=identity.product_id,
        revision_id=identity.revision_id,
        revision_version=revision.version,
        mapping_id=identity.mapping_id,
        topology=mapping.topology,
        connection_generation=identity.connection_generation,
        proposed_execution_id=identity.execution_id,
        old_baseline_execution_id=job.active_baseline_execution_id,
        sides=tuple(
            (
                side.repository_side,
                side.repository_id,
                side.active_commit_hash,
                side.proposed_commit_hash,
            )
            for side in candidate.sides
        ),
        files=tuple(
            (
                file.repository_side,
                file.ordinal,
                file.change,
                file.path,
            )
            for file in candidate.files
        ),
    )
    return candidate, digest


def _persist_rewrite_proposal(
    session: Session,
    *,
    identity: ImportExecutionIdentity,
    revision: ProductRevision,
    mapping: ProductRepositoryMapping,
    job: ImportJob,
    candidate: SourceRewriteCandidate,
    digest: str,
    now: datetime,
) -> ImportRewriteProposal:
    previous = session.execute(
        select(ImportRewriteProposal)
        .where(
            ImportRewriteProposal.import_job_id == identity.import_id,
            ImportRewriteProposal.status == "pending",
        )
        .with_for_update()
    ).scalar_one_or_none()
    if previous is not None:
        previous.status = "superseded"
        previous.resolved_at = now
        session.flush()

    sides = {side.repository_side: side for side in candidate.sides}
    direct = sides.get("direct")
    keys = sides.get("keys")
    translations = sides.get("translations")
    assert job.active_baseline_execution_id is not None
    proposal = ImportRewriteProposal(
        id=uuid4(),
        import_job_id=identity.import_id,
        product_id=identity.product_id,
        revision_id=identity.revision_id,
        revision_version=revision.version,
        mapping_id=identity.mapping_id,
        topology=mapping.topology,
        connection_generation=identity.connection_generation,
        proposed_execution_id=identity.execution_id,
        old_baseline_execution_id=job.active_baseline_execution_id,
        direct_repository_id=direct.repository_id if direct is not None else None,
        direct_old_commit_hash=(direct.active_commit_hash if direct is not None else None),
        direct_new_commit_hash=(direct.proposed_commit_hash if direct is not None else None),
        keys_repository_id=keys.repository_id if keys is not None else None,
        keys_old_commit_hash=keys.active_commit_hash if keys is not None else None,
        keys_new_commit_hash=keys.proposed_commit_hash if keys is not None else None,
        translations_repository_id=(
            translations.repository_id if translations is not None else None
        ),
        translations_old_commit_hash=(
            translations.active_commit_hash if translations is not None else None
        ),
        translations_new_commit_hash=(
            translations.proposed_commit_hash if translations is not None else None
        ),
        complete=True,
        digest=digest,
        status="pending",
    )
    session.add(proposal)
    session.flush()
    for position, file in enumerate(candidate.files):
        session.add(
            ImportRewriteDelta(
                proposal_id=proposal.id,
                position=position,
                repository_side=file.repository_side,
                change=file.change,
                path=file.path,
            )
        )
        session.flush()
    return proposal


def finish_import_execution(
    factory: sessionmaker[Session],
    *,
    identity: ImportExecutionIdentity,
    references: tuple[ImportSourceReferenceRecord, ...] | None,
    movement: SourceMovementClassification | None = None,
    canonical_manifest_digest: str | None = None,
    failure_category: ImportErrorCategory = "bounded_failure",
) -> bool:
    """Terminalize one execution, rolling canonical activation failures back first."""
    try:
        return _finish_import_execution_transaction(
            factory,
            identity=identity,
            references=references,
            movement=movement,
            canonical_manifest_digest=canonical_manifest_digest,
            failure_category=failure_category,
        )
    except Exception:
        if canonical_manifest_digest is None:
            raise
        return _terminalize_failed_canonical_activation(
            factory,
            identity=identity,
            failure_category=failure_category,
        )


def _terminalize_failed_canonical_activation(
    factory: sessionmaker[Session],
    *,
    identity: ImportExecutionIdentity,
    failure_category: ImportErrorCategory,
) -> bool:
    with factory.begin() as session:
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
            job is None
            or execution is None
            or job.current_execution_id != identity.execution_id
            or job.state != "running"
            or execution.state != "running"
        ):
            return False
        failed_at = datetime.now(UTC)
        execution.state = "failed"
        execution.finished_at = failed_at
        job.state = "import_failed"
        job.error_category = failure_category
        job.error_message = _public_failure_message(
            failure_category,
            has_baseline=job.active_baseline_execution_id is not None,
        )
        job.updated_at = failed_at
    return True


def _finish_import_execution_transaction(
    factory: sessionmaker[Session],
    *,
    identity: ImportExecutionIdentity,
    references: tuple[ImportSourceReferenceRecord, ...] | None,
    movement: SourceMovementClassification | None = None,
    canonical_manifest_digest: str | None = None,
    failure_category: ImportErrorCategory = "bounded_failure",
) -> bool:
    """Conditionally terminalize only the exact current execution and authority."""
    with factory.begin() as session:
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
        try:
            connection_generation = _connected_generation(session)
        except ImportConnectionUnavailable:
            connection_generation = None
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
            job is None
            or execution is None
            or job.current_execution_id != identity.execution_id
            or job.state != "running"
            or execution.state != "running"
        ):
            return False
        now = datetime.now(UTC)
        current_sides: tuple[ImportRepositorySideRecord, ...] | None = None
        if mapping is not None:
            try:
                current_sides = _mapping_sides(mapping)
            except ImportConflict:
                current_sides = None
        authority_is_current = (
            product is not None
            and product.is_active
            and product.active_revision_id == identity.revision_id
            and revision is not None
            and revision.is_published
            and mapping is not None
            and job.product_id == identity.product_id
            and job.revision_id == identity.revision_id
            and job.mapping_id == identity.mapping_id
            and job.topology == mapping.topology
            and connection_generation == identity.connection_generation
            and current_sides is not None
            and tuple(
                (side.role, side.repository_id, side.source_branch, side.localization_root)
                for side in current_sides
            )
            == tuple(
                (side.role, side.repository_id, side.source_branch, side.localization_root)
                for side in identity.repository_sides
            )
        )
        validated_references: tuple[ImportSourceReferenceRecord, ...] | None = None
        rewrite_authority: tuple[SourceRewriteCandidate, str] | None = None
        canonical_scope = None
        canonical_required = mapping is not None and mapping.base_language is not None
        if references is not None and authority_is_current:
            try:
                validated_references = _validated_references(identity, references)
                if canonical_required:
                    if canonical_manifest_digest is None:
                        raise ValueError("canonical manifest digest required")
                    if (
                        _source_references(
                            session,
                            execution_id=identity.execution_id,
                        )
                        != validated_references
                    ):
                        raise ValueError("canonical source references rejected")
                    assert mapping is not None
                    canonical_scope = session.execute(
                        select(LocalizationScope)
                        .where(
                            LocalizationScope.product_id == identity.product_id,
                            LocalizationScope.mapping_identity_key == mapping.identity_key,
                        )
                        .with_for_update()
                    ).scalar_one_or_none()
                    if canonical_scope is None:
                        raise ValueError("canonical scope rejected")
                    require_complete_staged_manifest(
                        session,
                        identity=identity,
                        manifest_digest=canonical_manifest_digest,
                    )
                if movement is not None:
                    baseline_references = (
                        _source_references(
                            session,
                            execution_id=job.active_baseline_execution_id,
                        )
                        if job.active_baseline_execution_id is not None
                        else ()
                    )
                    assert revision is not None
                    assert mapping is not None
                    rewrite_authority = _validated_rewrite_candidate(
                        identity=identity,
                        revision=revision,
                        mapping=mapping,
                        job=job,
                        references=validated_references,
                        baseline_references=baseline_references,
                        movement=movement,
                    )
            except ValueError:
                validated_references = None
                rewrite_authority = None

        if validated_references is None or not authority_is_current:
            execution.state = "failed"
            job.state = "import_failed"
            resolved_failure_category = (
                "connection_required"
                if not authority_is_current
                and connection_generation != identity.connection_generation
                else failure_category
            )
            job.error_category = resolved_failure_category
            job.error_message = _public_failure_message(
                resolved_failure_category,
                has_baseline=job.active_baseline_execution_id is not None,
            )
        else:
            baseline_matches = (
                job.active_baseline_execution_id is not None
                and _source_references(
                    session,
                    execution_id=job.active_baseline_execution_id,
                )
                == validated_references
            )
            if not canonical_required:
                for reference in validated_references:
                    session.add(
                        ImportSourceReference(
                            execution_id=identity.execution_id,
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
                # Legacy Phase 3 imports persist provenance in this final lock.
                session.flush()
            if canonical_required and rewrite_authority is None:
                assert canonical_scope is not None
                assert canonical_manifest_digest is not None
                activate_translation_dataset(
                    session,
                    identity=identity,
                    scope=canonical_scope,
                    job=job,
                    execution=execution,
                    manifest_digest=canonical_manifest_digest,
                    now=now,
                )
            else:
                execution.state = "succeeded"
                execution.finished_at = now
                job.state = "current"
                if rewrite_authority is None and not baseline_matches:
                    job.active_baseline_execution_id = execution.id
                job.error_category = None
                job.error_message = None
                session.flush()
            if rewrite_authority is not None:
                assert revision is not None
                assert mapping is not None
                candidate, digest = rewrite_authority
                _persist_rewrite_proposal(
                    session,
                    identity=identity,
                    revision=revision,
                    mapping=mapping,
                    job=job,
                    candidate=candidate,
                    digest=digest,
                    now=now,
                )
        execution.finished_at = now
        job.updated_at = now
    return True


def _rewrite_proposal_sides(
    proposal: ImportRewriteProposal,
) -> tuple[tuple[RepositoryRole, UUID, str, str], ...]:
    if proposal.topology == "direct":
        if (
            proposal.direct_repository_id is None
            or proposal.direct_old_commit_hash is None
            or proposal.direct_new_commit_hash is None
        ):
            raise ImportRewriteStale("import rewrite proposal stale")
        return (
            (
                "direct",
                proposal.direct_repository_id,
                proposal.direct_old_commit_hash,
                proposal.direct_new_commit_hash,
            ),
        )
    if proposal.topology == "separate":
        if (
            proposal.keys_repository_id is None
            or proposal.keys_old_commit_hash is None
            or proposal.keys_new_commit_hash is None
            or proposal.translations_repository_id is None
            or proposal.translations_old_commit_hash is None
            or proposal.translations_new_commit_hash is None
        ):
            raise ImportRewriteStale("import rewrite proposal stale")
        return (
            (
                "keys",
                proposal.keys_repository_id,
                proposal.keys_old_commit_hash,
                proposal.keys_new_commit_hash,
            ),
            (
                "translations",
                proposal.translations_repository_id,
                proposal.translations_old_commit_hash,
                proposal.translations_new_commit_hash,
            ),
        )
    raise ImportRewriteStale("import rewrite proposal stale")


def _current_rewrite_authority(
    session: Session,
    *,
    product_id: UUID,
    mapping_id: UUID,
    import_id: UUID,
    proposal_id: UUID | None,
    for_update: bool,
) -> tuple[
    ProductRevision,
    ProductRepositoryMapping,
    ImportJob,
    ImportRewriteProposal,
    ImportExecution,
    tuple[ImportRewriteDeltaRecord, ...],
]:
    """Load and revalidate one complete proposal under the confirmation lock order."""

    product_statement = select(Product).where(Product.id == product_id)
    if for_update:
        product_statement = product_statement.with_for_update()
    product = session.execute(product_statement).scalar_one_or_none()
    if product is None or product.deleted_at is not None or not product.is_active:
        raise ImportNotFound("published import unavailable")

    mapping_statement = (
        select(ProductRepositoryMapping)
        .options(selectinload(ProductRepositoryMapping.sides))
        .where(ProductRepositoryMapping.id == mapping_id)
    )
    if for_update:
        mapping_statement = mapping_statement.with_for_update()
    mapping = session.execute(mapping_statement).scalar_one_or_none()
    if mapping is None:
        raise ImportNotFound("published import unavailable")

    revision = session.execute(
        select(ProductRevision).where(
            ProductRevision.id == mapping.revision_id,
            ProductRevision.product_id == product_id,
        )
    ).scalar_one_or_none()
    if revision is None:
        raise ImportNotFound("published import unavailable")

    job_statement = select(ImportJob).where(
        ImportJob.id == import_id,
        ImportJob.product_id == product_id,
        ImportJob.revision_id == revision.id,
        ImportJob.mapping_id == mapping_id,
    )
    if for_update:
        job_statement = job_statement.with_for_update()
    job = session.execute(job_statement).scalar_one_or_none()
    if job is None:
        raise ImportNotFound("published import unavailable")

    proposal_statement = select(ImportRewriteProposal).where(
        ImportRewriteProposal.import_job_id == import_id,
        ImportRewriteProposal.mapping_id == mapping_id,
        ImportRewriteProposal.status == "pending",
    )
    if proposal_id is not None:
        proposal_statement = proposal_statement.where(ImportRewriteProposal.id == proposal_id)
    if for_update:
        proposal_statement = proposal_statement.with_for_update()
    proposal = session.execute(proposal_statement).scalar_one_or_none()
    if proposal is None:
        raise ImportRewriteStale("import rewrite proposal stale")

    proposed_execution_statement = select(ImportExecution).where(
        ImportExecution.id == proposal.proposed_execution_id,
        ImportExecution.import_job_id == import_id,
    )
    old_execution_statement = select(ImportExecution).where(
        ImportExecution.id == proposal.old_baseline_execution_id,
        ImportExecution.import_job_id == import_id,
    )
    if for_update:
        proposed_execution_statement = proposed_execution_statement.with_for_update()
        old_execution_statement = old_execution_statement.with_for_update()
    proposed_execution = session.execute(proposed_execution_statement).scalar_one_or_none()
    old_execution = session.execute(old_execution_statement).scalar_one_or_none()
    try:
        connection_generation = _connected_generation(session)
        mapping_sides = _mapping_sides(mapping)
    except (ImportConnectionUnavailable, ImportConflict) as error:
        raise ImportRewriteStale("import rewrite proposal stale") from error

    if (
        product.active_revision_id != revision.id
        or not revision.is_published
        or revision.version != proposal.revision_version
        or mapping.revision_id != revision.id
        or mapping.topology != proposal.topology
        or job.state != "current"
        or job.topology != proposal.topology
        or job.current_execution_id != proposal.proposed_execution_id
        or job.active_baseline_execution_id != proposal.old_baseline_execution_id
        or proposal.product_id != product_id
        or proposal.revision_id != revision.id
        or proposal.import_job_id != import_id
        or proposal.mapping_id != mapping_id
        or proposal.complete is not True
        or len(proposal.digest) != 64
        or any(character not in "0123456789abcdef" for character in proposal.digest)
        or connection_generation != proposal.connection_generation
        or proposed_execution is None
        or proposed_execution.state != "succeeded"
        or proposed_execution.connection_generation != proposal.connection_generation
        or old_execution is None
        or old_execution.state != "succeeded"
    ):
        raise ImportRewriteStale("import rewrite proposal stale")

    proposal_sides = _rewrite_proposal_sides(proposal)
    if tuple((side.role, side.repository_id) for side in mapping_sides) != tuple(
        (role, repository_id) for role, repository_id, _old, _new in proposal_sides
    ):
        raise ImportRewriteStale("import rewrite proposal stale")
    try:
        old_commits = _single_commit_per_side(
            _source_references(
                session,
                execution_id=proposal.old_baseline_execution_id,
            )
        )
        proposed_commits = _single_commit_per_side(
            _source_references(
                session,
                execution_id=proposal.proposed_execution_id,
            )
        )
    except ValueError as error:
        raise ImportRewriteStale("import rewrite proposal stale") from error
    if set(old_commits) != {side[0] for side in proposal_sides} or set(proposed_commits) != {
        side[0] for side in proposal_sides
    }:
        raise ImportRewriteStale("import rewrite proposal stale")
    for role, repository_id, old_commit, new_commit in proposal_sides:
        if old_commits[role] != (repository_id, old_commit) or proposed_commits[role] != (
            repository_id,
            new_commit,
        ):
            raise ImportRewriteStale("import rewrite proposal stale")

    delta_rows = tuple(
        session.scalars(
            select(ImportRewriteDelta)
            .where(ImportRewriteDelta.proposal_id == proposal.id)
            .order_by(ImportRewriteDelta.position)
        )
    )
    if len(delta_rows) > 500:
        raise ImportRewriteStale("import rewrite proposal stale")
    role_order = {role: index for index, (role, *_rest) in enumerate(proposal_sides)}
    last_role_index = -1
    seen_paths: set[tuple[RepositoryRole, str]] = set()
    deltas: list[ImportRewriteDeltaRecord] = []
    for expected_position, row in enumerate(delta_rows):
        role = cast(RepositoryRole, row.repository_side)
        change = cast(RewriteDeltaChange, row.change)
        try:
            path = validate_repository_relative_path(row.path)
        except ValueError as error:
            raise ImportRewriteStale("import rewrite proposal stale") from error
        if (
            row.position != expected_position
            or role not in role_order
            or role_order[role] < last_role_index
            or change not in {"added", "modified", "removed"}
            or path != row.path
            or not path.casefold().endswith((".xml", ".ts", ".json", ".strings"))
            or (role, path) in seen_paths
        ):
            raise ImportRewriteStale("import rewrite proposal stale")
        last_role_index = role_order[role]
        seen_paths.add((role, path))
        deltas.append(
            ImportRewriteDeltaRecord(
                position=row.position,
                repository_side=role,
                change=change,
                path=path,
            )
        )
    side_ordinals: dict[RepositoryRole, int] = {role: 0 for role in role_order}
    digest_files: list[tuple[RepositoryRole, int, RewriteDeltaChange, str]] = []
    for delta in deltas:
        digest_files.append(
            (
                delta.repository_side,
                side_ordinals[delta.repository_side],
                delta.change,
                delta.path,
            )
        )
        side_ordinals[delta.repository_side] += 1
    expected_digest = _rewrite_authority_digest(
        import_id=proposal.import_job_id,
        product_id=proposal.product_id,
        revision_id=proposal.revision_id,
        revision_version=proposal.revision_version,
        mapping_id=proposal.mapping_id,
        topology=proposal.topology,
        connection_generation=proposal.connection_generation,
        proposed_execution_id=proposal.proposed_execution_id,
        old_baseline_execution_id=proposal.old_baseline_execution_id,
        sides=proposal_sides,
        files=tuple(digest_files),
    )
    if proposal.digest != expected_digest:
        raise ImportRewriteStale("import rewrite proposal stale")
    return revision, mapping, job, proposal, proposed_execution, tuple(deltas)


def _rewrite_comparison_record(
    proposal: ImportRewriteProposal,
    deltas: tuple[ImportRewriteDeltaRecord, ...],
) -> ImportRewriteComparisonRecord:
    sides: list[ImportRewriteSideRecord] = []
    for role, repository_id, old_commit, new_commit in _rewrite_proposal_sides(proposal):
        side_deltas = tuple(delta for delta in deltas if delta.repository_side == role)
        sides.append(
            ImportRewriteSideRecord(
                repository_side=role,
                repository_id=repository_id,
                old_commit_hash=old_commit,
                new_commit_hash=new_commit,
                added_count=sum(delta.change == "added" for delta in side_deltas),
                modified_count=sum(delta.change == "modified" for delta in side_deltas),
                removed_count=sum(delta.change == "removed" for delta in side_deltas),
            )
        )
    return ImportRewriteComparisonRecord(
        proposal_id=proposal.id,
        import_id=proposal.import_job_id,
        mapping_id=proposal.mapping_id,
        proposed_execution_id=proposal.proposed_execution_id,
        proposal_digest=proposal.digest,
        topology=cast(Literal["direct", "separate"], proposal.topology),
        confirmable=True,
        sides=tuple(sides),
        files=deltas,
    )


def get_rewrite_comparison(
    session: Session,
    *,
    product_id: UUID,
    mapping_id: UUID,
    import_id: UUID,
) -> ImportRewriteComparisonRecord:
    """Return one complete, current, mapping-scoped rewrite comparison."""

    with session.begin():
        _revision, _mapping, _job, proposal, _execution, deltas = _current_rewrite_authority(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            import_id=import_id,
            proposal_id=None,
            for_update=False,
        )
        return _rewrite_comparison_record(proposal, deltas)


def _persisted_execution_identity(
    session: Session,
    *,
    mapping: ProductRepositoryMapping,
    job: ImportJob,
    execution: ImportExecution,
) -> ImportExecutionIdentity:
    execution_sides: list[ImportExecutionSide] = []
    for side in _mapping_sides(mapping):
        repository = session.get(Repository, side.repository_id)
        if repository is None:
            raise ImportRewriteStale("import rewrite proposal stale")
        execution_sides.append(
            ImportExecutionSide(
                role=side.role,
                repository_id=side.repository_id,
                workspace=repository.workspace,
                repository_slug=repository.repository_slug,
                source_branch=side.source_branch,
                localization_root=side.localization_root,
            )
        )
    return ImportExecutionIdentity(
        import_id=job.id,
        execution_id=execution.id,
        sequence=execution.sequence,
        product_id=job.product_id,
        revision_id=job.revision_id,
        mapping_id=job.mapping_id,
        connection_generation=execution.connection_generation,
        repository_sides=tuple(execution_sides),
    )


def confirm_rewrite_baseline(
    session: Session,
    *,
    product_id: UUID,
    mapping_id: UUID,
    import_id: UUID,
    proposal_id: UUID,
    proposed_execution_id: UUID,
    proposal_digest: str,
    actor_id: UUID,
) -> ImportJobRecord:
    """Atomically move one mapping baseline after full currentness revalidation."""

    if not isinstance(actor_id, UUID) or actor_id.int == 0:
        raise ImportRewriteStale("import rewrite proposal stale")
    with session.begin():
        _revision, mapping, job, proposal, proposed_execution, _deltas = _current_rewrite_authority(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            import_id=import_id,
            proposal_id=proposal_id,
            for_update=True,
        )
        if (
            proposal.proposed_execution_id != proposed_execution_id
            or proposal.digest != proposal_digest
            or proposed_execution.id != proposed_execution_id
        ):
            raise ImportRewriteStale("import rewrite proposal stale")
        confirmed_at = datetime.now(UTC)
        identity = _persisted_execution_identity(
            session,
            mapping=mapping,
            job=job,
            execution=proposed_execution,
        )
        if mapping.base_language is None:
            job.active_baseline_execution_id = proposed_execution_id
            job.updated_at = confirmed_at
        else:
            scope = session.execute(
                select(LocalizationScope)
                .where(
                    LocalizationScope.product_id == product_id,
                    LocalizationScope.mapping_identity_key == mapping.identity_key,
                )
                .with_for_update()
            ).scalar_one_or_none()
            if scope is None:
                raise ImportRewriteStale("import rewrite proposal stale")
            try:
                manifest_digest = staged_manifest_digest(session, identity=identity)
                activate_translation_dataset(
                    session,
                    identity=identity,
                    scope=scope,
                    job=job,
                    execution=proposed_execution,
                    manifest_digest=manifest_digest,
                    now=confirmed_at,
                )
            except TranslationImportRejected as error:
                raise ImportRewriteStale("import rewrite proposal stale") from error
        proposal.status = "confirmed"
        proposal.resolved_at = confirmed_at
        proposal.confirmed_by = actor_id
        session.flush()
        return _record(
            session,
            product_id=product_id,
            mapping=mapping,
            job=job,
            capability=_current_import_capability(session),
        )


def require_current_import_baseline(
    session: Session,
    *,
    product_id: UUID,
    mapping_id: UUID,
    execution_id: UUID,
) -> ImportBaselineRecord:
    """Require an immutable execution to remain the current mapping baseline."""

    product = session.get(Product, product_id)
    mapping = session.execute(
        _published_mapping_statement(
            product_id=product_id,
            mapping_id=mapping_id,
        )
    ).scalar_one_or_none()
    job = session.execute(
        select(ImportJob).where(
            ImportJob.product_id == product_id,
            ImportJob.mapping_id == mapping_id,
        )
    ).scalar_one_or_none()
    execution = session.execute(
        select(ImportExecution).where(
            ImportExecution.id == execution_id,
            ImportExecution.import_job_id == (job.id if job is not None else UUID(int=0)),
        )
    ).scalar_one_or_none()
    if (
        product is None
        or product.deleted_at is not None
        or not product.is_active
        or product.active_revision_id is None
        or mapping is None
        or job is None
        or job.revision_id != product.active_revision_id
        or job.active_baseline_execution_id != execution_id
        or execution is None
        or execution.state != "succeeded"
        or execution.finished_at is None
    ):
        raise ImportConflict("import baseline is not current")
    return ImportBaselineRecord(
        imported_at=execution.finished_at,
        source_references=_source_references(session, execution_id=execution_id),
    )


def reconcile_stale_imports(
    factory: sessionmaker[Session],
    *,
    hard_time_limit_seconds: int,
    watchdog_grace_seconds: int,
    clock: ImportClock = lambda: datetime.now(UTC),
) -> int:
    """Fail one locked batch of current executions abandoned by workers."""
    if hard_time_limit_seconds <= 0 or watchdog_grace_seconds <= 0:
        raise ValueError("import watchdog limits must be positive")
    finished_at = clock()
    if finished_at.tzinfo is None or finished_at.utcoffset() is None:
        raise ValueError("import watchdog clock must be timezone-aware")
    finished_at = finished_at.astimezone(UTC)
    cutoff = finished_at - timedelta(seconds=hard_time_limit_seconds + watchdog_grace_seconds)
    reconciled = 0
    with factory.begin() as session:
        stale_execution_ids = tuple(
            session.scalars(
                select(ImportExecution.id)
                .join(
                    ImportJob,
                    (ImportJob.id == ImportExecution.import_job_id)
                    & (ImportJob.current_execution_id == ImportExecution.id),
                )
                .where(
                    ImportExecution.state == "running",
                    ImportExecution.started_at <= cutoff,
                    ImportJob.state == "running",
                )
                .order_by(ImportExecution.started_at, ImportExecution.id)
                .limit(IMPORT_WATCHDOG_BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
        )
        for execution_id in stale_execution_ids:
            execution = session.get(ImportExecution, execution_id)
            if execution is None or execution.state != "running":
                continue
            job = session.execute(
                select(ImportJob)
                .where(
                    ImportJob.id == execution.import_job_id,
                    ImportJob.current_execution_id == execution.id,
                    ImportJob.state == "running",
                )
                .with_for_update(skip_locked=True)
            ).scalar_one_or_none()
            if job is None:
                continue
            execution.state = "failed"
            execution.finished_at = finished_at
            job.state = "import_failed"
            job.error_category = "timeout"
            job.error_message = _public_failure_message(
                "timeout",
                has_baseline=job.active_baseline_execution_id is not None,
            )
            job.updated_at = finished_at
            reconciled += 1
    return reconciled


def execute_import_job(
    factory: sessionmaker[Session],
    *,
    import_id: UUID,
    processor: ImportProcessor,
) -> None:
    """Run one current execution and conditionally terminalize the same record."""
    identity = start_import_execution(factory, import_id=import_id)
    if identity is None:
        return
    started_at = time.monotonic()
    try:
        processed = processor(identity)
        if isinstance(processed, ImportProcessingResult):
            references = _validated_references(identity, processed.references)
            movement = processed.movement
            canonical_manifest_digest = processed.canonical_manifest_digest
        else:
            references = _validated_references(identity, processed)
            movement = None
            canonical_manifest_digest = None
    except BitbucketProviderReadError as error:
        terminalized = finish_import_execution(
            factory,
            identity=identity,
            references=None,
            failure_category=_provider_failure_category(error.kind),
        )
        if terminalized:
            log_bitbucket_operation_failure(
                context=BitbucketDiagnosticContext(
                    import_id=identity.import_id,
                    execution_number=identity.sequence,
                ),
                operation=error.operation or BitbucketOperation.SOURCE_TREE,
                error_category=error.kind,
                provider_status=error.provider_status,
                elapsed_ms=(time.monotonic() - started_at) * 1000,
            )
    except Exception:
        finish_import_execution(
            factory,
            identity=identity,
            references=None,
            failure_category="bounded_failure",
        )
    else:
        finish_import_execution(
            factory,
            identity=identity,
            references=references,
            movement=movement,
            canonical_manifest_digest=canonical_manifest_digest,
        )


async def _process_import(
    identity: ImportExecutionIdentity,
    *,
    factory: sessionmaker[Session],
    adapter: SourceDiscoveryAdapter,
) -> ImportProcessingResult:
    references: list[ImportSourceReferenceRecord] = []
    source_contents: dict[tuple[RepositoryRole, str], bytes] = {}
    for side in identity.repository_sides:
        repository = RepositoryRecord(
            id=side.repository_id,
            workspace=side.workspace,
            repository_slug=side.repository_slug,
            descriptive_name=None,
        )
        with factory() as session:
            snapshot = await discover_repository_sources_for_record(
                session,
                repository=repository,
                branch=side.source_branch,
                adapter=adapter,
                localization_root=side.localization_root,
            )
        for source_file in snapshot.files:
            source_contents[(side.role, source_file.path)] = source_file.content
            references.append(
                ImportSourceReferenceRecord(
                    position=len(references),
                    repository_side=side.role,
                    repository_id=side.repository_id,
                    source_branch=side.source_branch,
                    commit_hash=snapshot.commit_hash,
                    path=source_file.path,
                    size_bytes=len(source_file.content),
                    sha256=hashlib.sha256(source_file.content).hexdigest(),
                )
            )
    durable_references = tuple(references)
    with factory() as session:
        canonical_import_enabled = _canonical_import_enabled(
            session,
            identity=identity,
        )
        parser_inputs = _confirmed_parser_inputs(
            session,
            identity=identity,
            source_contents=source_contents,
        )
    if not canonical_import_enabled:
        return ImportProcessingResult(references=durable_references)
    if parser_inputs:
        from verboflex.localization.duplicate_diagnostics import inspect_duplicate_keys
        from verboflex.services.duplicate_reports import store_report

        report = inspect_duplicate_keys(parser_inputs)
        with factory.begin() as session:
            owner = session.scalar(
                select(ImportExecution)
                .where(ImportExecution.id == identity.execution_id)
                .with_for_update()
            )
            job = session.get(ImportJob, identity.import_id)
            if (
                owner is not None
                and owner.state == "running"
                and owner.sequence == identity.sequence
                and job is not None
                and job.current_execution_id == identity.execution_id
            ):
                source_summaries = list(
                    {
                        (
                            ref.repository_side,
                            ref.repository_id,
                            ref.source_branch,
                            ref.commit_hash,
                        ): dict(
                            repository_side=ref.repository_side,
                            repository_id=str(ref.repository_id),
                            source_branch=ref.source_branch,
                            commit_hash=ref.commit_hash,
                        )
                        for ref in durable_references
                    }.values()
                )
                store_report(
                    session,
                    report=report,
                    sources=source_summaries,
                    execution_id=identity.execution_id,
                )
        parse_result = parse_canonical_mapping(parser_inputs)
        if not parse_result.issues and (report.groups or not report.complete):
            parse_result = CanonicalParseResult(
                issues=(
                    CanonicalIssue(
                        code="duplicate_key" if report.groups else "unsupported_structure",
                        repository_side=parser_inputs[0].repository_side,
                        path=parser_inputs[0].path,
                        message="Duplicate localization key."
                        if report.groups
                        else "Diagnostic scan is incomplete.",
                    ),
                )
            )
    else:
        parse_result = CanonicalParseResult(
            issues=(
                CanonicalIssue(
                    code="malformed_file",
                    repository_side=identity.repository_sides[0].role,
                    path="<input>",
                    message="Canonical parser input is invalid.",
                ),
            )
        )
    manifest = stage_translation_parse(
        factory,
        identity=identity,
        references=durable_references,
        result=parse_result,
    )
    if manifest is None:
        raise ValueError("canonical import execution is stale")
    return ImportProcessingResult(
        references=durable_references,
        canonical_manifest_digest=manifest.digest,
    )


def _canonical_import_enabled(
    session: Session,
    *,
    identity: ImportExecutionIdentity,
) -> bool:
    return (
        session.scalar(
            select(ProductRepositoryMapping.base_language).where(
                ProductRepositoryMapping.id == identity.mapping_id,
                ProductRepositoryMapping.revision_id == identity.revision_id,
            )
        )
        is not None
    )


def _confirmed_parser_inputs(
    session: Session,
    *,
    identity: ImportExecutionIdentity,
    source_contents: dict[tuple[RepositoryRole, str], bytes],
) -> tuple[CanonicalParserInput, ...]:
    revision = session.get(ProductRevision, identity.revision_id)
    mapping = session.execute(
        select(ProductRepositoryMapping)
        .options(selectinload(ProductRepositoryMapping.sides))
        .where(
            ProductRepositoryMapping.id == identity.mapping_id,
            ProductRepositoryMapping.revision_id == identity.revision_id,
        )
    ).scalar_one_or_none()
    if (
        revision is None
        or mapping is None
        or mapping.base_language is None
        or mapping.confirmed_preview_job_id is None
        or mapping.selected_layout_candidate_id is None
        or mapping.selected_layout_version != 1
        or not is_current_preview_confirmation(session, revision, mapping)
    ):
        return ()
    preview_job = session.get(PreviewJob, mapping.confirmed_preview_job_id)
    if preview_job is None or preview_job.result is None:
        return ()
    raw_candidates = preview_job.result.get("layout_candidates")
    if not isinstance(raw_candidates, list):
        return ()
    try:
        candidates = tuple(layout_candidate_from_mapping(candidate) for candidate in raw_candidates)
    except KeyError, TypeError, ValueError:
        return ()
    selected = tuple(
        candidate
        for candidate in candidates
        if candidate.id == mapping.selected_layout_candidate_id
        and candidate.version == mapping.selected_layout_version
    )
    if len(selected) != 1:
        return ()
    selected_candidate = selected[0]
    expected_selected_side = "direct" if mapping.topology == "direct" else "translations"
    if (
        selected_candidate.repository_side != expected_selected_side
        or mapping.base_language not in selected_candidate.languages
    ):
        return ()

    candidates_by_side: dict[RepositoryRole, PreviewLayoutCandidate] = {
        expected_selected_side: selected_candidate
    }
    if mapping.topology == "separate":
        keys_candidates = tuple(
            candidate
            for candidate in candidates
            if candidate.repository_side == "keys"
            and candidate.format == selected_candidate.format
            and mapping.base_language in candidate.languages
        )
        if len(keys_candidates) != 1:
            return ()
        candidates_by_side["keys"] = keys_candidates[0]

    parser_inputs: list[CanonicalParserInput] = []
    for side in identity.repository_sides:
        candidate = candidates_by_side.get(side.role)
        if candidate is None:
            return ()
        current_files = tuple(
            (path, content)
            for (role, path), content in sorted(source_contents.items())
            if role == side.role and _path_belongs_to_confirmed_layout(candidate, path)
        )
        if not current_files:
            return ()
        for path, content in current_files:
            parser_inputs.append(
                CanonicalParserInput(
                    format=candidate.format,
                    repository_side=side.role,
                    path=path,
                    content=content,
                    layout_identity=candidate.layout_identity,
                    layout_version=candidate.version,
                    base_language=mapping.base_language,
                )
            )
    return tuple(parser_inputs)


def _path_belongs_to_confirmed_layout(candidate: PreviewLayoutCandidate, path: str) -> bool:
    """Select current files, never treating a historical preview list as a manifest.

    Layout templates are immutable confirmation authority. Content and locale
    validity remain the canonical parser's responsibility, including malformed
    new files and structures the read-only preview grammar cannot represent.
    """
    layout = candidate.layout_identity
    if candidate.format == "android_xml":
        return re.fullmatch(re.escape(layout) + r"/values[^/]*/[^/]+\.xml", path) is not None
    if candidate.format == "json" and layout.startswith("json:locale-rooted:"):
        return path == layout.removeprefix("json:locale-rooted:")
    template_prefixes = {
        "json": "json:flat-per-locale:",
        "qt_ts": "qt-ts:",
        "ios_strings": "ios-strings:",
    }
    prefix = template_prefixes.get(candidate.format)
    if prefix is None or not layout.startswith(prefix):
        return False
    template = layout.removeprefix(prefix)
    pattern = re.escape(template).replace(re.escape("{locale}"), r"[^/]+")
    return re.fullmatch(pattern, path) is not None


async def classify_import_movement(
    identity: ImportExecutionIdentity,
    *,
    references: tuple[ImportSourceReferenceRecord, ...],
    factory: sessionmaker[Session],
    adapter: SourceDiscoveryAdapter,
) -> SourceMovementClassification | None:
    """Return complete rewrite authority for a current imported baseline, if needed."""
    validated = _validated_references(identity, references)
    with factory() as session:
        job = session.get(ImportJob, identity.import_id)
        if job is None or job.active_baseline_execution_id is None:
            return None
        baseline_references = _source_references(
            session,
            execution_id=job.active_baseline_execution_id,
        )
        baseline_commits = _single_commit_per_side(baseline_references)
        proposed_commits = _single_commit_per_side(validated)
        sources: list[SourceMovementInput] = []
        for side in identity.repository_sides:
            baseline = baseline_commits.get(side.role)
            proposed = proposed_commits.get(side.role)
            if (
                baseline is None
                or proposed is None
                or baseline[0] != side.repository_id
                or proposed[0] != side.repository_id
            ):
                raise ValueError("import movement references rejected")
            sources.append(
                SourceMovementInput(
                    repository_side=side.role,
                    repository_id=side.repository_id,
                    workspace=side.workspace,
                    repository_slug=side.repository_slug,
                    active_commit_hash=baseline[1],
                    proposed_commit_hash=proposed[1],
                )
            )
    with factory() as provider_session:
        movement = await classify_source_movement(
            provider_session,
            sources=tuple(sources),
            adapter=adapter,
        )
    return movement if movement.movement == "review-required" else None


def process_import(
    identity: ImportExecutionIdentity,
    *,
    factory: sessionmaker[Session],
    adapter: SourceDiscoveryAdapter,
) -> tuple[ImportSourceReferenceRecord, ...]:
    """Resolve branches once and retain only exact ordered content metadata."""
    import asyncio

    return asyncio.run(_process_import(identity, factory=factory, adapter=adapter)).references
