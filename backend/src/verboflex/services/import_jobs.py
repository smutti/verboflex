"""Published-mapping imports with durable UUID-only execution."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, NoReturn, Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import select
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
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.import_job import (
    ImportExecution,
    ImportJob,
    ImportRewriteDelta,
    ImportRewriteProposal,
    ImportSourceReference,
)
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.repository import Repository
from verboflex.services.bitbucket_oauth import PULLREQUEST_WRITE_SCOPE
from verboflex.services.repositories import RepositoryRecord
from verboflex.services.repository_discovery import (
    SourceDiscoveryAdapter,
    discover_repository_sources_for_record,
)

IMPORT_TASK_NAME = "verboflex.import.run"
IMPORT_WATCHDOG_BATCH_SIZE = 100
IMPORT_FAILURE_CATEGORY = "provider_unavailable"
IMPORT_FAILURE_WITHOUT_BASELINE = (
    "This import did not complete. Review the reason, then retry from the mapping. "
    "No import baseline was created."
)
IMPORT_FAILURE_WITH_BASELINE = (
    "This import did not complete. Review the reason, then retry from the mapping. "
    "The last successful baseline is unchanged."
)

ImportState = Literal[
    "not_imported",
    "queued",
    "running",
    "current",
    "import_failed",
]
RepositoryRole = Literal["direct", "keys", "translations"]
SourceMovementRelation = Literal["equal", "descendant", "diverged"]
SourceMovementKind = Literal["equal", "fast-forward", "review-required"]
RewriteDeltaChange = Literal["added", "modified", "removed"]


class ImportNotFound(LookupError):
    """Raised when published import authority is unavailable."""


class ImportConflict(ValueError):
    """Raised when persisted import state disagrees with current authority."""


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
class ImportJobRecord:
    """Closed public projection of one published mapping and its logical import."""

    id: UUID | None
    mapping_id: UUID
    active_revision_id: UUID
    topology: Literal["direct", "separate"]
    repository_sides: tuple[ImportRepositorySideRecord, ...]
    state: ImportState
    active_baseline: ImportBaselineRecord | None
    latest_execution_at: datetime | None
    retry_count: int
    error_category: Literal["provider_unavailable"] | None
    error_message: str | None


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


ImportProcessor = Callable[[ImportExecutionIdentity], tuple[ImportSourceReferenceRecord, ...]]
ImportClock = Callable[[], datetime]


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
        if comparison.relation != "diverged":
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
    if product is None or not product.is_active or product.active_revision_id is None:
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


def _record(
    session: Session,
    *,
    mapping: ProductRepositoryMapping,
    job: ImportJob | None,
) -> ImportJobRecord:
    sides = _mapping_sides(mapping)
    if job is None:
        return ImportJobRecord(
            id=None,
            mapping_id=mapping.id,
            active_revision_id=mapping.revision_id,
            topology=cast(Literal["direct", "separate"], mapping.topology),
            repository_sides=sides,
            state="not_imported",
            active_baseline=None,
            latest_execution_at=None,
            retry_count=0,
            error_category=None,
            error_message=None,
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
    return ImportJobRecord(
        id=job.id,
        mapping_id=job.mapping_id,
        active_revision_id=job.revision_id,
        topology=cast(Literal["direct", "separate"], job.topology),
        repository_sides=sides,
        state=cast(ImportState, job.state),
        active_baseline=baseline,
        latest_execution_at=job.latest_execution_at,
        retry_count=job.retry_count,
        error_category=cast(
            Literal["provider_unavailable"] | None,
            job.error_category,
        ),
        error_message=job.error_message,
    )


def list_published_mapping_imports(
    session: Session,
    *,
    product_id: UUID,
) -> tuple[ImportJobRecord, ...]:
    """List direct mappings from the exact active published revision in server order."""
    with session.begin():
        product = session.get(Product, product_id)
        if product is None or not product.is_active or product.active_revision_id is None:
            raise ImportNotFound("published imports unavailable")
        mappings = tuple(
            session.execute(_published_mapping_statement(product_id=product_id)).scalars()
        )
        jobs = {
            job.mapping_id: job
            for job in session.execute(
                select(ImportJob).where(ImportJob.revision_id == product.active_revision_id)
            ).scalars()
        }
        return tuple(
            _record(session, mapping=mapping, job=jobs.get(mapping.id)) for mapping in mappings
        )


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
        elif job.state not in {"queued", "running"}:
            raise ImportConflict("persisted import state rejected")
        record = _record(session, mapping=mapping, job=job)

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
                job.error_category = IMPORT_FAILURE_CATEGORY
                job.error_message = (
                    IMPORT_FAILURE_WITH_BASELINE
                    if job.active_baseline_execution_id is not None
                    else IMPORT_FAILURE_WITHOUT_BASELINE
                )
                job.updated_at = now
            mapping = session.execute(
                select(ProductRepositoryMapping)
                .options(selectinload(ProductRepositoryMapping.sides))
                .where(ProductRepositoryMapping.id == job.mapping_id)
            ).scalar_one()
            record = _record(session, mapping=mapping, job=job)
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
        product = session.get(Product, product_id)
        job = session.get(ImportJob, import_id)
        if (
            product is None
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
        return _record(session, mapping=mapping, job=job)


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
                        )
                    )
        now = datetime.now(UTC)
        if not authority_is_current:
            if execution is not None and execution.state == "queued":
                execution.state = "failed"
                execution.started_at = now
                execution.finished_at = now
            job.state = "import_failed"
            job.error_category = IMPORT_FAILURE_CATEGORY
            job.error_message = (
                IMPORT_FAILURE_WITH_BASELINE
                if job.active_baseline_execution_id is not None
                else IMPORT_FAILURE_WITHOUT_BASELINE
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
            and tuple((side.role, side.repository_id, side.source_branch) for side in current_sides)
            == tuple(
                (side.role, side.repository_id, side.source_branch)
                for side in identity.repository_sides
            )
        )
        validated_references: tuple[ImportSourceReferenceRecord, ...] | None = None
        rewrite_authority: tuple[SourceRewriteCandidate, str] | None = None
        if references is not None and authority_is_current:
            try:
                validated_references = _validated_references(identity, references)
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
            job.error_category = IMPORT_FAILURE_CATEGORY
            job.error_message = (
                IMPORT_FAILURE_WITH_BASELINE
                if job.active_baseline_execution_id is not None
                else IMPORT_FAILURE_WITHOUT_BASELINE
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
    if product is None or not product.is_active:
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

    proposed_execution = session.execute(
        select(ImportExecution).where(
            ImportExecution.id == proposal.proposed_execution_id,
            ImportExecution.import_job_id == import_id,
        )
    ).scalar_one_or_none()
    old_execution = session.execute(
        select(ImportExecution).where(
            ImportExecution.id == proposal.old_baseline_execution_id,
            ImportExecution.import_job_id == import_id,
        )
    ).scalar_one_or_none()
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
        job.active_baseline_execution_id = proposed_execution_id
        job.updated_at = confirmed_at
        proposal.status = "confirmed"
        proposal.resolved_at = confirmed_at
        proposal.confirmed_by = actor_id
        session.flush()
        return _record(session, mapping=mapping, job=job)


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
            job.error_category = IMPORT_FAILURE_CATEGORY
            job.error_message = (
                IMPORT_FAILURE_WITH_BASELINE
                if job.active_baseline_execution_id is not None
                else IMPORT_FAILURE_WITHOUT_BASELINE
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
        references = _validated_references(identity, processor(identity))
    except BitbucketProviderReadError as error:
        terminalized = finish_import_execution(factory, identity=identity, references=None)
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
        finish_import_execution(factory, identity=identity, references=None)
    else:
        finish_import_execution(factory, identity=identity, references=references)


async def _process_import(
    identity: ImportExecutionIdentity,
    *,
    factory: sessionmaker[Session],
    adapter: SourceDiscoveryAdapter,
) -> tuple[ImportSourceReferenceRecord, ...]:
    references: list[ImportSourceReferenceRecord] = []
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
            )
        for source_file in snapshot.files:
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
    return tuple(references)


def process_import(
    identity: ImportExecutionIdentity,
    *,
    factory: sessionmaker[Session],
    adapter: SourceDiscoveryAdapter,
) -> tuple[ImportSourceReferenceRecord, ...]:
    """Resolve branches once and retain only exact ordered content metadata."""
    import asyncio

    return asyncio.run(_process_import(identity, factory=factory, adapter=adapter))
