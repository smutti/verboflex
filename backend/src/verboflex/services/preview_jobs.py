"""Durable preview job identity, idempotency, and conditional state transitions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import func, null, select, update
from sqlalchemy.orm import Session, selectinload, sessionmaker

from verboflex.audit.ledger import record_audit
from verboflex.core.config import get_settings
from verboflex.integrations.bitbucket.client import BitbucketProviderReadError
from verboflex.localization.preview.core import (
    normalize_preview_locale,
    validate_layout_candidate_mappings,
)
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.preview_job import (
    ActiveRevisionRevalidationConfirmation,
    PreviewJob,
)
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.services.bitbucket_oauth import PULLREQUEST_WRITE_SCOPE
from verboflex.services.repository_capabilities import PublicReadAuthority, is_public_github_mapping

PREVIEW_TASK_NAME = "verboflex.preview.run"
PREVIEW_DETECTOR_VERSION = "preview-canonical-quarantine-v2"
PREVIEW_LAYOUT_IDENTITY = "automatic-layout-discovery-v2"
PREVIEW_WATCHDOG_BATCH_SIZE = 100
MAX_RESULT_BYTES = 1_048_576

PreviewJobState = Literal["queued", "running", "succeeded", "failed", "timed_out"]
PreviewRevisionScope = Literal["candidate", "active_revalidation"]
PreviewJobErrorCode = Literal[
    "enqueue_failed",
    "processing_failed",
    "stale_attempt",
    "stale_candidate",
    "stale_connection",
    "stale_identity",
    "time_limit_exceeded",
]
RepositoryRole = Literal["direct", "keys", "translations"]
PreviewDiagnosticCode = Literal["repository_scan_limit_reached"]

_PREVIEW_JOB_STATES = {"queued", "running", "succeeded", "failed", "timed_out"}
_PREVIEW_ERROR_CODES = {
    "enqueue_failed",
    "processing_failed",
    "stale_attempt",
    "stale_candidate",
    "stale_connection",
    "stale_identity",
    "time_limit_exceeded",
}
_PREVIEW_RESULT_FIELDS = {"detector_version", "digest", "layout_candidates"}
_PREVIEW_DIAGNOSTIC_CODES = {"repository_scan_limit_reached"}


class PreviewJobNotFound(LookupError):
    """Raised when the requested job or candidate mapping is unavailable."""


class PreviewJobConflict(ValueError):
    """Raised when submitted identity disagrees with current durable authority."""


class PreviewBaseLanguageRequired(PreviewJobConflict):
    """Raised when a candidate has no one server-proven base-language selection."""


class PreviewConnectionUnavailable(RuntimeError):
    """Raised when there is no connected repository-read credential generation."""


class PreviewJobTimedOut(TimeoutError):
    """Raised by the worker timeout adapter to request a durable timeout state."""


@dataclass(frozen=True, slots=True)
class PreviewConfirmationRecord:
    """One explicit historical assignment of a current exact layout."""

    job_id: UUID
    mapping_id: UUID
    preview_digest: str
    layout_candidate_id: UUID
    layout_candidate_version: Literal[1]
    base_language: str
    confirmed_by: UUID
    confirmed_at: datetime


@dataclass(frozen=True, slots=True)
class ActiveRevisionRevalidationConfirmationRecord:
    """One immutable explicit confirmation of an exact published revision job."""

    job_id: UUID
    product_id: UUID
    revision_id: UUID
    revision_version: int
    mapping_id: UUID
    connection_generation: int
    preview_digest: str
    layout_candidate_id: UUID
    layout_candidate_version: Literal[1]
    base_language: str
    confirmed_by: UUID
    confirmed_at: datetime


@dataclass(frozen=True, slots=True)
class ActiveRevisionMappingEligibility:
    """Bounded currentness result for one published mapping."""

    mapping_id: UUID
    is_current: bool
    blocker_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ActiveRevisionRevalidationEligibility:
    """Read-only all-mapping reactivation eligibility projection."""

    product_id: UUID
    active_revision_id: UUID
    active_revision_version: int
    eligible: bool
    blocker_codes: tuple[str, ...]
    mappings: tuple[ActiveRevisionMappingEligibility, ...]


class PreviewEnqueuer(Protocol):
    """Persisted-job transport seam whose only input is the durable UUID."""

    def __call__(self, job_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class PreviewRepositorySide:
    """One exact role/repository/branch/commit member of preview identity."""

    role: RepositoryRole
    repository_id: UUID
    source_branch: str
    commit_hash: str
    localization_root: str | None = None


@dataclass(frozen=True, slots=True)
class PreviewJobIdentity:
    """Complete immutable pre-detector identity loaded by a UUID-only worker."""

    job_id: UUID
    input_digest: str
    attempt: int
    revision_scope: PreviewRevisionScope
    product_id: UUID
    candidate_revision_id: UUID
    candidate_revision_version: int
    mapping_id: UUID
    topology: Literal["direct", "separate"]
    connection_generation: int
    detector_version: str
    layout_identity: str
    repository_sides: tuple[PreviewRepositorySide, ...]


@dataclass(frozen=True, slots=True)
class PreviewJobRecord:
    """Closed public projection backed only by PostgreSQL state."""

    id: UUID
    input_digest: str
    attempt: int
    state: PreviewJobState
    revision_scope: PreviewRevisionScope
    product_id: UUID
    candidate_revision_id: UUID
    candidate_revision_version: int
    mapping_id: UUID
    connection_generation: int
    detector_version: str
    repository_sides: tuple[PreviewRepositorySide, ...]
    result: dict[str, object] | None
    error_code: PreviewJobErrorCode | None
    diagnostic_code: PreviewDiagnosticCode | None
    is_current: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


PreviewProcessor = Callable[[PreviewJobIdentity], Mapping[str, object]]
PreviewClock = Callable[[], datetime]


def _exact_commit_hash(raw: object) -> str:
    if (
        not isinstance(raw, str)
        or len(raw) != 40
        or any(character not in "0123456789abcdefABCDEF" for character in raw)
    ):
        raise PreviewJobConflict("preview commit identity rejected")
    return raw.lower()


def _repository_sides(row: PreviewJob) -> tuple[PreviewRepositorySide, ...]:
    try:
        sides = tuple(
            PreviewRepositorySide(
                role=cast(RepositoryRole, side["role"]),
                repository_id=UUID(side["repository_id"]),
                source_branch=side["source_branch"],
                commit_hash=side["commit_hash"],
                localization_root=side.get("localization_root"),
            )
            for side in row.repository_sides
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PreviewJobConflict("persisted preview identity rejected") from error
    if not sides:
        raise PreviewJobConflict("persisted preview identity rejected")
    return sides


def _record(row: PreviewJob, *, is_current: bool) -> PreviewJobRecord:
    if row.state not in _PREVIEW_JOB_STATES:
        raise PreviewJobConflict("persisted preview state rejected")
    if row.error_code is not None and row.error_code not in _PREVIEW_ERROR_CODES:
        raise PreviewJobConflict("persisted preview error rejected")
    if row.diagnostic_code is not None and row.diagnostic_code not in _PREVIEW_DIAGNOSTIC_CODES:
        raise PreviewJobConflict("persisted preview diagnostic rejected")
    identity = _identity(row)
    result = None if row.result is None else _closed_result(identity, row.result)
    return PreviewJobRecord(
        id=row.id,
        input_digest=row.input_digest,
        attempt=row.attempt,
        state=cast(PreviewJobState, row.state),
        revision_scope=cast(PreviewRevisionScope, row.revision_scope),
        product_id=row.product_id,
        candidate_revision_id=row.candidate_revision_id,
        candidate_revision_version=row.candidate_revision_version,
        mapping_id=row.mapping_id,
        connection_generation=row.connection_generation,
        detector_version=row.detector_version,
        repository_sides=_repository_sides(row),
        result=result,
        error_code=cast(PreviewJobErrorCode | None, row.error_code),
        diagnostic_code=cast(PreviewDiagnosticCode | None, row.diagnostic_code),
        is_current=is_current,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _identity(row: PreviewJob) -> PreviewJobIdentity:
    if row.topology not in {"direct", "separate"}:
        raise PreviewJobConflict("persisted preview topology rejected")
    if row.revision_scope not in {"candidate", "active_revalidation"}:
        raise PreviewJobConflict("persisted preview scope rejected")
    return PreviewJobIdentity(
        job_id=row.id,
        input_digest=row.input_digest,
        attempt=row.attempt,
        revision_scope=cast(PreviewRevisionScope, row.revision_scope),
        product_id=row.product_id,
        candidate_revision_id=row.candidate_revision_id,
        candidate_revision_version=row.candidate_revision_version,
        mapping_id=row.mapping_id,
        topology=cast(Literal["direct", "separate"], row.topology),
        connection_generation=row.connection_generation,
        detector_version=row.detector_version,
        layout_identity=row.layout_identity,
        repository_sides=_repository_sides(row),
    )


def _closed_result(
    identity: PreviewJobIdentity,
    raw_result: Mapping[str, object],
) -> dict[str, object]:
    """Validate the exact pre-detector result envelope before persistence or projection."""
    if set(raw_result) != _PREVIEW_RESULT_FIELDS:
        raise ValueError("preview result rejected")
    detector_version = raw_result.get("detector_version")
    digest = raw_result.get("digest")
    layout_candidates = raw_result.get("layout_candidates")
    if (
        detector_version != identity.detector_version
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("preview result rejected")
    try:
        candidates = validate_layout_candidate_mappings(layout_candidates)
    except ValueError as error:
        raise ValueError("preview result rejected") from error
    complete_digest = _complete_preview_digest(identity, candidates)
    if digest not in {identity.input_digest, complete_digest}:
        raise ValueError("preview result rejected")
    return {
        "detector_version": detector_version,
        "digest": complete_digest,
        "layout_candidates": candidates,
    }


def _complete_preview_digest(
    identity: PreviewJobIdentity,
    layout_candidates: list[dict[str, object]],
    *,
    base_language: str | None = None,
) -> str:
    """Hash the exact attempt, pre-detector authority, and canonical detector output."""
    payload = {
        "attempt": identity.attempt,
        "candidate_revision_id": str(identity.candidate_revision_id),
        "candidate_revision_version": identity.candidate_revision_version,
        "connection_generation": identity.connection_generation,
        "detector_version": identity.detector_version,
        "input_digest": identity.input_digest,
        "job_id": str(identity.job_id),
        "layout_candidates": layout_candidates,
        "layout_identity": identity.layout_identity,
        "mapping_id": str(identity.mapping_id),
        "product_id": str(identity.product_id),
        "repository_sides": [
            {
                "commit_hash": side.commit_hash,
                "repository_id": str(side.repository_id),
                "role": side.role,
                "source_branch": side.source_branch,
                **(
                    {"localization_root": side.localization_root}
                    if side.localization_root is not None
                    else {}
                ),
            }
            for side in identity.repository_sides
        ],
        "topology": identity.topology,
    }
    if base_language is not None:
        payload["base_language"] = base_language
    if identity.revision_scope == "active_revalidation":
        payload["revision_scope"] = identity.revision_scope
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()


def _confirmation_digest_matches(
    identity: PreviewJobIdentity,
    layout_candidates: list[dict[str, object]],
    *,
    base_language: str,
    expected_digest: str,
) -> bool:
    """Compare one persisted confirmation with its full language-bound authority."""
    return (
        _complete_preview_digest(
            identity,
            layout_candidates,
            base_language=base_language,
        )
        == expected_digest
    )


def _matches_started_identity(row: PreviewJob, identity: PreviewJobIdentity) -> bool:
    """Compare every immutable field captured before processor execution."""
    try:
        return _identity(row) == identity
    except PreviewJobConflict:
        return False


def _claim_current_running_attempt(
    session: Session,
    *,
    job_id: UUID,
    attempt: int,
    connection_generation: int,
    finished_at: datetime,
) -> bool:
    """Terminalize one exact running UUID/attempt/generation through a database CAS."""
    terminal_id = session.scalar(
        update(PreviewJob)
        .where(
            PreviewJob.id == job_id,
            PreviewJob.attempt == attempt,
            PreviewJob.connection_generation == connection_generation,
            PreviewJob.state == "running",
        )
        .values(
            state="timed_out",
            result=null(),
            error_code="time_limit_exceeded",
            finished_at=finished_at,
            updated_at=finished_at,
        )
        .returning(PreviewJob.id)
        .execution_options(synchronize_session=False)
    )
    return terminal_id is not None


def reconcile_stale_preview_jobs(
    factory: sessionmaker[Session],
    *,
    hard_time_limit_seconds: int,
    watchdog_grace_seconds: int,
    clock: PreviewClock = lambda: datetime.now(UTC),
) -> int:
    """Claim one indexed batch of stale running attempts and time them out durably."""
    if hard_time_limit_seconds <= 0 or watchdog_grace_seconds <= 0:
        raise ValueError("preview watchdog limits must be positive")
    finished_at = clock()
    if finished_at.tzinfo is None or finished_at.utcoffset() is None:
        raise ValueError("preview watchdog clock must be timezone-aware")
    finished_at = finished_at.astimezone(UTC)
    cutoff = finished_at - timedelta(seconds=hard_time_limit_seconds + watchdog_grace_seconds)
    reconciled = 0
    with factory.begin() as session:
        attempts = session.execute(
            select(
                PreviewJob.id,
                PreviewJob.attempt,
                PreviewJob.connection_generation,
            )
            .where(
                PreviewJob.state == "running",
                PreviewJob.started_at <= cutoff,
            )
            .order_by(PreviewJob.started_at, PreviewJob.id)
            .limit(PREVIEW_WATCHDOG_BATCH_SIZE)
            .with_for_update(skip_locked=True)
        ).all()
        for job_id, attempt, connection_generation in attempts:
            if _claim_current_running_attempt(
                session,
                job_id=job_id,
                attempt=attempt,
                connection_generation=connection_generation,
                finished_at=finished_at,
            ):
                reconciled += 1
    return reconciled


def _canonical_identity(
    *,
    product_id: UUID,
    revision: ProductRevision,
    mapping: ProductRepositoryMapping,
    connection_generation: int,
    repository_sides: list[dict[str, str]],
) -> tuple[str, str]:
    payload = {
        "candidate_revision_id": str(revision.id),
        "candidate_revision_version": revision.version,
        "connection_generation": connection_generation,
        "detector_version": PREVIEW_DETECTOR_VERSION,
        "layout_identity": PREVIEW_LAYOUT_IDENTITY,
        "mapping_id": str(mapping.id),
        "product_id": str(product_id),
        "repository_sides": repository_sides,
        "topology": mapping.topology,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return encoded, hashlib.sha256(encoded.encode("ascii")).hexdigest()


def _active_revalidation_identity(
    *,
    product_id: UUID,
    revision: ProductRevision,
    mapping: ProductRepositoryMapping,
    connection_generation: int,
    repository_sides: list[dict[str, str]],
) -> tuple[str, str]:
    """Domain-separate published-revision work without changing candidate bytes."""
    payload = {
        "active_revision_id": str(revision.id),
        "active_revision_version": revision.version,
        "connection_generation": connection_generation,
        "detector_version": PREVIEW_DETECTOR_VERSION,
        "layout_identity": PREVIEW_LAYOUT_IDENTITY,
        "mapping_id": str(mapping.id),
        "product_id": str(product_id),
        "repository_sides": repository_sides,
        "revision_scope": "active_revalidation",
        "topology": mapping.topology,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return encoded, hashlib.sha256(encoded.encode("ascii")).hexdigest()


def _locked_mapping(
    session: Session,
    *,
    product_id: UUID,
    mapping_id: UUID,
    expected_candidate_version: int,
) -> tuple[ProductRevision, ProductRepositoryMapping]:
    product = session.execute(
        select(Product)
        .where(Product.id == product_id, Product.deleted_at.is_(None))
        .with_for_update()
    ).scalar_one_or_none()
    if product is None or product.candidate_revision_id is None:
        raise PreviewJobNotFound("preview candidate unavailable")
    revision = session.execute(
        select(ProductRevision)
        .where(ProductRevision.id == product.candidate_revision_id)
        .with_for_update()
    ).scalar_one()
    if revision.is_published or revision.version != expected_candidate_version:
        raise PreviewJobConflict("preview candidate conflict")
    mapping = session.execute(
        select(ProductRepositoryMapping)
        .options(selectinload(ProductRepositoryMapping.sides))
        .where(
            ProductRepositoryMapping.id == mapping_id,
            ProductRepositoryMapping.revision_id == revision.id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if mapping is None or mapping.topology not in {"direct", "separate"}:
        raise PreviewJobNotFound("preview mapping unavailable")
    return revision, mapping


def _locked_active_revision_mapping(
    session: Session,
    *,
    product_id: UUID,
    active_revision_id: UUID,
    mapping_id: UUID,
    expected_active_revision_version: int,
) -> tuple[ProductRevision, ProductRepositoryMapping]:
    product = session.execute(
        select(Product)
        .where(Product.id == product_id, Product.deleted_at.is_(None))
        .with_for_update()
    ).scalar_one_or_none()
    if (
        product is None
        or product.is_active
        or product.active_revision_id != active_revision_id
        or product.candidate_revision_id is not None
    ):
        raise PreviewJobNotFound("active revision revalidation unavailable")
    revision = session.execute(
        select(ProductRevision)
        .where(
            ProductRevision.id == active_revision_id,
            ProductRevision.product_id == product_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if (
        revision is None
        or not revision.is_published
        or revision.version != expected_active_revision_version
    ):
        raise PreviewJobConflict("active revision revalidation conflict")
    mapping = session.execute(
        select(ProductRepositoryMapping)
        .options(selectinload(ProductRepositoryMapping.sides))
        .where(
            ProductRepositoryMapping.id == mapping_id,
            ProductRepositoryMapping.revision_id == revision.id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if mapping is None or mapping.topology not in {"direct", "separate"}:
        raise PreviewJobNotFound("active revision mapping unavailable")
    return revision, mapping


def _connected_generation(session: Session, mapping: ProductRepositoryMapping | None = None) -> int:
    if is_public_github_mapping(session, mapping):
        return 0
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
        raise PreviewConnectionUnavailable("preview connection unavailable")
    return connection.generation


def _complete_sides(
    mapping: ProductRepositoryMapping,
    raw_commits: object,
) -> list[dict[str, str]]:
    commits = _validated_commits(raw_commits)
    persisted_sides = sorted(mapping.sides, key=lambda side: side.role)
    expected_roles = {side.role for side in persisted_sides}
    _require_mapping_roles(mapping, submitted_roles=set(commits), expected_roles=expected_roles)
    return [
        {
            "role": side.role,
            "repository_id": str(side.repository_id),
            "source_branch": side.source_branch,
            "commit_hash": commits[side.role],
            **(
                {"localization_root": side.localization_root}
                if side.localization_root is not None
                else {}
            ),
        }
        for side in persisted_sides
    ]


def _validated_commits(raw_commits: object) -> dict[str, str]:
    if isinstance(raw_commits, (str, bytes)) or not isinstance(raw_commits, Mapping):
        raise PreviewJobConflict("preview commit identity rejected")
    commits: dict[str, str] = {}
    for raw_role, raw_commit in raw_commits.items():
        if raw_role not in {"direct", "keys", "translations"} or raw_role in commits:
            raise PreviewJobConflict("preview commit identity rejected")
        commits[cast(str, raw_role)] = _exact_commit_hash(raw_commit)
    return commits


def _require_mapping_roles(
    mapping: ProductRepositoryMapping,
    *,
    submitted_roles: set[str],
    expected_roles: set[str],
) -> None:
    if submitted_roles != expected_roles:
        raise PreviewJobConflict("preview commit identity rejected")
    if mapping.topology == "direct" and expected_roles != {"direct"}:
        raise PreviewJobConflict("preview mapping identity rejected")
    if mapping.topology == "separate" and expected_roles != {"keys", "translations"}:
        raise PreviewJobConflict("preview mapping identity rejected")


def enqueue_preview_job(job_id: UUID) -> None:
    """Send one JSON task containing only the durable job UUID."""
    from verboflex.worker.celery_app import app

    settings = get_settings()
    app.send_task(
        PREVIEW_TASK_NAME,
        args=[str(job_id)],
        task_id=str(job_id),
        serializer="json",
        soft_time_limit=settings.preview_soft_time_limit_seconds,
        time_limit=settings.preview_hard_time_limit_seconds,
    )


def create_or_reuse_preview_job(
    session: Session,
    *,
    actor_id: UUID | None,
    product_id: UUID,
    mapping_id: UUID,
    expected_candidate_version: int,
    commits: object,
    enqueuer: PreviewEnqueuer = enqueue_preview_job,
) -> PreviewJobRecord:
    """Persist or reuse complete identity, then enqueue a newly committed UUID."""
    created = False
    with session.begin():
        revision, mapping = _locked_mapping(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=expected_candidate_version,
        )
        connection_generation = _connected_generation(session, mapping)
        repository_sides = _complete_sides(mapping, commits)
        _encoded_identity, input_digest = _canonical_identity(
            product_id=product_id,
            revision=revision,
            mapping=mapping,
            connection_generation=connection_generation,
            repository_sides=repository_sides,
        )
        latest = session.execute(
            select(PreviewJob)
            .where(PreviewJob.input_digest == input_digest)
            .order_by(PreviewJob.attempt.desc())
            .limit(1)
            .with_for_update()
        ).scalar_one_or_none()
        if latest is not None and latest.state not in {"failed", "timed_out"}:
            row = latest
        else:
            row = PreviewJob(
                id=uuid4(),
                input_digest=input_digest,
                attempt=1 if latest is None else latest.attempt + 1,
                state="queued",
                revision_scope="candidate",
                product_id=product_id,
                candidate_revision_id=revision.id,
                candidate_revision_version=revision.version,
                mapping_id=mapping.id,
                topology=mapping.topology,
                connection_generation=connection_generation,
                detector_version=PREVIEW_DETECTOR_VERSION,
                layout_identity=PREVIEW_LAYOUT_IDENTITY,
                repository_sides=repository_sides,
            )
            session.add(row)
            session.flush()
            record_audit(session, actor_id=actor_id, action="preview.requested", entity_id=row.id)
            created = True
        record = _record(
            row,
            is_current=_current_failure_code(session, row, for_update=True) is None,
        )

    if not created:
        return record
    try:
        enqueuer(record.id)
    except Exception:
        with session.begin():
            row = session.execute(
                select(PreviewJob).where(PreviewJob.id == record.id).with_for_update()
            ).scalar_one()
            if row.state == "queued":
                row.state = "failed"
                row.error_code = "enqueue_failed"
                row.finished_at = datetime.now(UTC)
                row.updated_at = row.finished_at
            record = _record(
                row,
                is_current=_current_failure_code(session, row, for_update=True) is None,
            )
    return record


def create_or_reuse_active_revision_revalidation_job(
    session: Session,
    *,
    actor_id: UUID | None,
    product_id: UUID,
    active_revision_id: UUID,
    mapping_id: UUID,
    expected_active_revision_version: int,
    commits: object,
    enqueuer: PreviewEnqueuer = enqueue_preview_job,
) -> PreviewJobRecord:
    """Persist or reuse read-only work for one exact inactive published mapping."""
    created = False
    with session.begin():
        revision, mapping = _locked_active_revision_mapping(
            session,
            product_id=product_id,
            active_revision_id=active_revision_id,
            mapping_id=mapping_id,
            expected_active_revision_version=expected_active_revision_version,
        )
        connection_generation = _connected_generation(session, mapping)
        repository_sides = _complete_sides(mapping, commits)
        _encoded_identity, input_digest = _active_revalidation_identity(
            product_id=product_id,
            revision=revision,
            mapping=mapping,
            connection_generation=connection_generation,
            repository_sides=repository_sides,
        )
        latest = session.execute(
            select(PreviewJob)
            .where(
                PreviewJob.input_digest == input_digest,
                PreviewJob.revision_scope == "active_revalidation",
            )
            .order_by(PreviewJob.attempt.desc())
            .limit(1)
            .with_for_update()
        ).scalar_one_or_none()
        if latest is not None and latest.state not in {"failed", "timed_out"}:
            row = latest
        else:
            row = PreviewJob(
                id=uuid4(),
                input_digest=input_digest,
                attempt=1 if latest is None else latest.attempt + 1,
                state="queued",
                revision_scope="active_revalidation",
                product_id=product_id,
                candidate_revision_id=revision.id,
                candidate_revision_version=revision.version,
                mapping_id=mapping.id,
                topology=mapping.topology,
                connection_generation=connection_generation,
                detector_version=PREVIEW_DETECTOR_VERSION,
                layout_identity=PREVIEW_LAYOUT_IDENTITY,
                repository_sides=repository_sides,
            )
            session.add(row)
            session.flush()
            record_audit(session, actor_id=actor_id, action="preview.requested", entity_id=row.id)
            created = True
        record = _record(
            row,
            is_current=_current_failure_code(session, row, for_update=True) is None,
        )

    if not created:
        return record
    try:
        enqueuer(record.id)
    except Exception:
        with session.begin():
            row = session.execute(
                select(PreviewJob).where(PreviewJob.id == record.id).with_for_update()
            ).scalar_one()
            if row.state == "queued":
                row.state = "failed"
                row.error_code = "enqueue_failed"
                row.finished_at = datetime.now(UTC)
                row.updated_at = row.finished_at
            record = _record(
                row,
                is_current=_current_failure_code(session, row, for_update=True) is None,
            )
    return record


def get_preview_job(session: Session, *, job_id: UUID) -> PreviewJobRecord:
    """Read one bounded status/result from PostgreSQL, never Celery state."""
    with session.begin():
        row = session.get(PreviewJob, job_id)
        if row is None:
            raise PreviewJobNotFound("preview job unavailable")
        product = session.get(Product, row.product_id)
        if product is None or product.deleted_at is not None:
            raise PreviewJobNotFound("preview job unavailable")
        if row.revision_scope != "candidate":
            raise PreviewJobConflict("preview identity conflict")
        return _record(
            row,
            is_current=_current_failure_code(session, row, for_update=False) is None,
        )


def get_latest_candidate_preview_job(
    session: Session,
    *,
    product_id: UUID,
    mapping_id: UUID,
) -> PreviewJobRecord:
    """Rediscover the newest job for one exact current candidate mapping."""
    with session.begin():
        product = session.execute(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        ).scalar_one_or_none()
        if product is None or product.candidate_revision_id is None:
            raise PreviewJobNotFound("preview candidate unavailable")
        revision = session.execute(
            select(ProductRevision).where(
                ProductRevision.id == product.candidate_revision_id,
                ProductRevision.product_id == product_id,
                ProductRevision.is_published.is_(False),
            )
        ).scalar_one_or_none()
        if revision is None:
            raise PreviewJobNotFound("preview candidate unavailable")
        mapping_exists = session.scalar(
            select(ProductRepositoryMapping.id).where(
                ProductRepositoryMapping.id == mapping_id,
                ProductRepositoryMapping.revision_id == revision.id,
            )
        )
        if mapping_exists is None:
            raise PreviewJobNotFound("preview mapping unavailable")
        row = session.execute(
            select(PreviewJob)
            .where(
                PreviewJob.product_id == product_id,
                PreviewJob.candidate_revision_id == revision.id,
                PreviewJob.candidate_revision_version == revision.version,
                PreviewJob.mapping_id == mapping_id,
                PreviewJob.revision_scope == "candidate",
            )
            .order_by(PreviewJob.created_at.desc(), PreviewJob.attempt.desc(), PreviewJob.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            raise PreviewJobNotFound("preview job unavailable")
        return _record(
            row,
            is_current=_current_failure_code(session, row, for_update=False) is None,
        )


def get_active_revision_revalidation_job(
    session: Session,
    *,
    job_id: UUID,
) -> PreviewJobRecord:
    """Read one bounded active-revalidation job from PostgreSQL."""
    with session.begin():
        row = session.get(PreviewJob, job_id)
        if row is None or row.revision_scope != "active_revalidation":
            raise PreviewJobNotFound("active revalidation job unavailable")
        product = session.get(Product, row.product_id)
        if product is None or product.deleted_at is not None:
            raise PreviewJobNotFound("active revalidation job unavailable")
        return _record(
            row,
            is_current=_current_failure_code(session, row, for_update=False) is None,
        )


def get_latest_active_revision_revalidation_job(
    session: Session,
    *,
    product_id: UUID,
    active_revision_id: UUID,
    mapping_id: UUID,
) -> PreviewJobRecord:
    """Rediscover the newest job for one exact inactive published mapping."""
    with session.begin():
        product = session.execute(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        ).scalar_one_or_none()
        if (
            product is None
            or product.is_active
            or product.active_revision_id != active_revision_id
            or product.candidate_revision_id is not None
        ):
            raise PreviewJobNotFound("active revision revalidation unavailable")
        revision = session.execute(
            select(ProductRevision).where(
                ProductRevision.id == active_revision_id,
                ProductRevision.product_id == product_id,
                ProductRevision.is_published.is_(True),
            )
        ).scalar_one_or_none()
        if revision is None:
            raise PreviewJobNotFound("active revision revalidation unavailable")
        mapping_exists = session.scalar(
            select(ProductRepositoryMapping.id).where(
                ProductRepositoryMapping.id == mapping_id,
                ProductRepositoryMapping.revision_id == revision.id,
            )
        )
        if mapping_exists is None:
            raise PreviewJobNotFound("active revision mapping unavailable")
        row = session.execute(
            select(PreviewJob)
            .where(
                PreviewJob.product_id == product_id,
                PreviewJob.candidate_revision_id == revision.id,
                PreviewJob.candidate_revision_version == revision.version,
                PreviewJob.mapping_id == mapping_id,
                PreviewJob.revision_scope == "active_revalidation",
            )
            .order_by(PreviewJob.created_at.desc(), PreviewJob.attempt.desc(), PreviewJob.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            raise PreviewJobNotFound("active revalidation job unavailable")
        return _record(
            row,
            is_current=_current_failure_code(session, row, for_update=False) is None,
        )


def _require_selected_layout_candidate(
    candidates: list[dict[str, object]],
    *,
    layout_candidate_id: UUID,
    layout_candidate_version: Literal[1],
    expected_side: str,
    unavailable_message: str,
) -> dict[str, object]:
    """Resolve exactly one submitted candidate on the mapping's repository side."""
    matches = [
        candidate
        for candidate in candidates
        if candidate["id"] == str(layout_candidate_id)
        and candidate["version"] == layout_candidate_version
    ]
    if len(matches) != 1 or matches[0]["repository_side"] != expected_side:
        raise PreviewJobConflict(unavailable_message)
    return matches[0]


def _candidate_languages(candidate: dict[str, object]) -> tuple[str, ...]:
    """Validate detected locales; default-only layouts have no labelled locale."""
    raw_languages = candidate.get("languages")
    if not isinstance(raw_languages, list) or not raw_languages:
        raise PreviewBaseLanguageRequired("base_language_required")
    languages = tuple(
        language for language in cast(list[object], raw_languages) if language != "default"
    )
    if any(
        not isinstance(language, str) or normalize_preview_locale(language) != language
        for language in languages
    ):
        raise PreviewBaseLanguageRequired("base_language_required")
    return cast(tuple[str, ...], languages)


def _resolve_base_language(
    candidate: dict[str, object],
    *,
    submitted: str | None,
) -> str:
    """Require a declared locale for default files, otherwise prove detected membership."""
    languages = _candidate_languages(candidate)
    has_default = "default" in cast(list[str], candidate["languages"])
    if submitted is None:
        if has_default or len(languages) != 1:
            raise PreviewBaseLanguageRequired("base_language_required")
        return languages[0]
    if normalize_preview_locale(submitted) != submitted or (
        not has_default and submitted not in languages
    ):
        raise PreviewJobConflict("preview identity conflict")
    return submitted


def _candidate_has_base_language(candidate: dict[str, object], base_language: str) -> bool:
    try:
        return _resolve_base_language(candidate, submitted=base_language) == base_language
    except PreviewJobConflict:
        return False


def confirm_preview_job(
    session: Session,
    *,
    job_id: UUID,
    preview_digest: str,
    layout_candidate_id: UUID,
    layout_candidate_version: Literal[1],
    base_language: str | None = None,
    actor_id: UUID,
) -> PreviewConfirmationRecord:
    """Assign exactly one current succeeded candidate under durable authority locks."""
    with session.begin():
        row = session.execute(
            select(PreviewJob).where(PreviewJob.id == job_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise PreviewJobNotFound("preview job unavailable")
        if row.revision_scope != "candidate":
            raise PreviewJobConflict("preview identity conflict")
        if _current_failure_code(session, row, for_update=True) is not None:
            raise PreviewJobConflict("preview identity conflict")
        if row.state != "succeeded" or row.result is None:
            raise PreviewJobConflict("preview confirmation unavailable")
        result = _closed_result(_identity(row), row.result)
        if result["digest"] != preview_digest:
            raise PreviewJobConflict("preview identity conflict")
        raw_candidates = cast(list[dict[str, object]], result["layout_candidates"])
        mapping = _current_mapping(session, row, for_update=True)
        assert mapping is not None
        expected_side = "direct" if mapping.topology == "direct" else "translations"
        candidate = _require_selected_layout_candidate(
            raw_candidates,
            layout_candidate_id=layout_candidate_id,
            layout_candidate_version=layout_candidate_version,
            expected_side=expected_side,
            unavailable_message="preview confirmation unavailable",
        )
        selected_base_language = _resolve_base_language(candidate, submitted=base_language)
        confirmation_digest = _complete_preview_digest(
            _identity(row),
            raw_candidates,
            base_language=selected_base_language,
        )
        if (
            mapping.confirmed_preview_job_id == row.id
            and mapping.confirmed_preview_digest == confirmation_digest
            and mapping.selected_layout_candidate_id == layout_candidate_id
            and mapping.selected_layout_version == layout_candidate_version
            and mapping.base_language == selected_base_language
            and mapping.preview_confirmed_by is not None
            and mapping.preview_confirmed_at is not None
        ):
            return PreviewConfirmationRecord(
                job_id=row.id,
                mapping_id=mapping.id,
                preview_digest=confirmation_digest,
                layout_candidate_id=layout_candidate_id,
                layout_candidate_version=layout_candidate_version,
                base_language=selected_base_language,
                confirmed_by=mapping.preview_confirmed_by,
                confirmed_at=mapping.preview_confirmed_at,
            )
        if _mapping_has_any_confirmation(mapping):
            raise PreviewJobConflict("preview identity conflict")
        confirmed_at = datetime.now(UTC)
        mapping.base_language = selected_base_language
        mapping.selected_layout_candidate_id = layout_candidate_id
        mapping.selected_layout_version = layout_candidate_version
        mapping.confirmed_preview_job_id = row.id
        mapping.confirmed_preview_digest = confirmation_digest
        mapping.preview_confirmed_by = actor_id
        mapping.preview_confirmed_at = confirmed_at
        mapping.updated_at = confirmed_at
        session.flush()
        return PreviewConfirmationRecord(
            job_id=row.id,
            mapping_id=mapping.id,
            preview_digest=confirmation_digest,
            layout_candidate_id=layout_candidate_id,
            layout_candidate_version=layout_candidate_version,
            base_language=selected_base_language,
            confirmed_by=actor_id,
            confirmed_at=confirmed_at,
        )


def confirm_active_revision_revalidation(
    session: Session,
    *,
    job_id: UUID,
    preview_digest: str,
    layout_candidate_id: UUID,
    layout_candidate_version: Literal[1],
    base_language: str | None = None,
    actor_id: UUID,
) -> ActiveRevisionRevalidationConfirmationRecord:
    """Persist immutable explicit evidence without mutating the published graph."""
    with session.begin():
        row = session.execute(
            select(PreviewJob).where(PreviewJob.id == job_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise PreviewJobNotFound("active revalidation job unavailable")
        if row.revision_scope != "active_revalidation":
            raise PreviewJobConflict("active revalidation identity conflict")
        if _current_failure_code(session, row, for_update=True) is not None:
            raise PreviewJobConflict("active revalidation identity conflict")
        if row.state != "succeeded" or row.result is None:
            raise PreviewJobConflict("active revalidation confirmation unavailable")
        result = _closed_result(_identity(row), row.result)
        if result["digest"] != preview_digest:
            raise PreviewJobConflict("active revalidation identity conflict")
        candidates = cast(list[dict[str, object]], result["layout_candidates"])
        revision = _current_revision(session, row, for_update=True)
        mapping = _current_mapping(session, row, for_update=True)
        assert revision is not None
        assert mapping is not None
        expected_side = "direct" if mapping.topology == "direct" else "translations"
        candidate = _require_selected_layout_candidate(
            candidates,
            layout_candidate_id=layout_candidate_id,
            layout_candidate_version=layout_candidate_version,
            expected_side=expected_side,
            unavailable_message="active revalidation confirmation unavailable",
        )
        selected_base_language = _resolve_base_language(candidate, submitted=base_language)
        if mapping.base_language is None:
            raise PreviewBaseLanguageRequired("base_language_required")
        if mapping.base_language != selected_base_language:
            raise PreviewJobConflict("active revalidation identity conflict")
        if (
            mapping.selected_layout_candidate_id != layout_candidate_id
            or mapping.selected_layout_version != layout_candidate_version
        ):
            raise PreviewJobConflict("active revalidation confirmation unavailable")
        confirmation_digest = _complete_preview_digest(
            _identity(row),
            candidates,
            base_language=selected_base_language,
        )
        existing = session.get(ActiveRevisionRevalidationConfirmation, row.id)
        if existing is not None:
            if not _sidecar_matches_confirmation_request(
                existing,
                row=row,
                confirmation_digest=confirmation_digest,
                layout_candidate_id=layout_candidate_id,
                layout_candidate_version=layout_candidate_version,
            ):
                raise PreviewJobConflict("active revalidation confirmation conflict")
            return _active_confirmation_record(
                existing,
                base_language=selected_base_language,
            )
        confirmed_at = datetime.now(UTC)
        sidecar = ActiveRevisionRevalidationConfirmation(
            job_id=row.id,
            revision_scope="active_revalidation",
            product_id=row.product_id,
            revision_id=row.candidate_revision_id,
            revision_version=row.candidate_revision_version,
            mapping_id=row.mapping_id,
            connection_generation=row.connection_generation,
            preview_digest=confirmation_digest,
            layout_candidate_id=layout_candidate_id,
            layout_candidate_version=layout_candidate_version,
            confirmed_by=actor_id,
            confirmed_at=confirmed_at,
        )
        session.add(sidecar)
        session.flush()
        return _active_confirmation_record(
            sidecar,
            base_language=selected_base_language,
        )


def _active_confirmation_record(
    row: ActiveRevisionRevalidationConfirmation,
    *,
    base_language: str,
) -> ActiveRevisionRevalidationConfirmationRecord:
    if row.preview_digest is None:
        raise PreviewJobConflict("active revalidation confirmation conflict")
    return ActiveRevisionRevalidationConfirmationRecord(
        job_id=row.job_id,
        product_id=row.product_id,
        revision_id=row.revision_id,
        revision_version=row.revision_version,
        mapping_id=row.mapping_id,
        connection_generation=row.connection_generation,
        preview_digest=row.preview_digest,
        layout_candidate_id=row.layout_candidate_id,
        layout_candidate_version=cast(Literal[1], row.layout_candidate_version),
        base_language=base_language,
        confirmed_by=row.confirmed_by,
        confirmed_at=row.confirmed_at,
    )


def _sidecar_matches_confirmation_request(
    sidecar: ActiveRevisionRevalidationConfirmation,
    *,
    row: PreviewJob,
    confirmation_digest: str,
    layout_candidate_id: UUID,
    layout_candidate_version: Literal[1],
) -> bool:
    return (
        sidecar.revision_scope == "active_revalidation"
        and sidecar.product_id == row.product_id
        and sidecar.revision_id == row.candidate_revision_id
        and sidecar.revision_version == row.candidate_revision_version
        and sidecar.mapping_id == row.mapping_id
        and sidecar.connection_generation == row.connection_generation
        and sidecar.preview_digest == confirmation_digest
        and sidecar.layout_candidate_id == layout_candidate_id
        and sidecar.layout_candidate_version == layout_candidate_version
    )


def is_current_preview_confirmation(
    session: Session,
    revision: ProductRevision,
    mapping: ProductRepositoryMapping,
) -> bool:
    """Recompute one exact confirmation against current durable authority."""
    if _mapping_has_complete_confirmation(mapping):
        assert mapping.confirmed_preview_job_id is not None
        row = session.get(PreviewJob, mapping.confirmed_preview_job_id)
        if row is not None and _confirmation_job_matches(row, revision, mapping):
            connection = _current_connection(session, row, for_update=True)
            if (
                connection is not None
                and _confirmation_job_is_latest(session, row)
                and _current_identity_matches(row, revision, mapping, connection)
                and _confirmed_layout_matches(row, mapping)
            ):
                return True
    return active_revision_revalidation_is_current(session, revision, mapping)


def active_revision_revalidation_is_current(
    session: Session,
    revision: ProductRevision,
    mapping: ProductRepositoryMapping,
) -> bool:
    """Accept only explicit sidecar evidence for the exact latest active job."""
    sidecars = session.execute(
        select(ActiveRevisionRevalidationConfirmation)
        .where(
            ActiveRevisionRevalidationConfirmation.product_id == revision.product_id,
            ActiveRevisionRevalidationConfirmation.revision_id == revision.id,
            ActiveRevisionRevalidationConfirmation.mapping_id == mapping.id,
        )
        .order_by(
            ActiveRevisionRevalidationConfirmation.confirmed_at.desc(),
            ActiveRevisionRevalidationConfirmation.job_id.desc(),
        )
    ).scalars()
    for sidecar in sidecars:
        row = session.get(PreviewJob, sidecar.job_id)
        if row is None or not _active_confirmation_job_matches(
            sidecar,
            row=row,
            revision=revision,
            mapping=mapping,
        ):
            continue
        connection = _current_connection(session, row, for_update=True)
        if (
            connection is not None
            and _current_failure_code(session, row, for_update=True) is None
            and _confirmation_job_is_latest(session, row)
            and _current_identity_matches(row, revision, mapping, connection)
            and _active_confirmed_layout_matches(sidecar, row=row, mapping=mapping)
        ):
            return True
    return False


def _active_confirmation_job_matches(
    sidecar: ActiveRevisionRevalidationConfirmation,
    *,
    row: PreviewJob,
    revision: ProductRevision,
    mapping: ProductRepositoryMapping,
) -> bool:
    return (
        row.revision_scope == "active_revalidation"
        and sidecar.revision_scope == "active_revalidation"
        and row.state == "succeeded"
        and row.result is not None
        and sidecar.product_id == revision.product_id == row.product_id
        and sidecar.revision_id == revision.id == row.candidate_revision_id
        and sidecar.revision_version == revision.version == row.candidate_revision_version
        and sidecar.mapping_id == mapping.id == row.mapping_id
        and sidecar.connection_generation == row.connection_generation
        and mapping.revision_id == revision.id
    )


def _active_confirmed_layout_matches(
    sidecar: ActiveRevisionRevalidationConfirmation,
    *,
    row: PreviewJob,
    mapping: ProductRepositoryMapping,
) -> bool:
    assert row.result is not None
    try:
        result = _closed_result(_identity(row), row.result)
    except PreviewJobConflict, ValueError:
        return False
    if mapping.base_language is None:
        return False
    candidates = cast(list[dict[str, object]], result["layout_candidates"])
    if not _confirmation_digest_matches(
        _identity(row),
        candidates,
        base_language=mapping.base_language,
        expected_digest=sidecar.preview_digest,
    ):
        return False
    return (
        mapping.selected_layout_candidate_id == sidecar.layout_candidate_id
        and mapping.selected_layout_version == sidecar.layout_candidate_version
        and _selected_layout_matches(candidates, mapping)
    )


def get_active_revision_revalidation_eligibility(
    session: Session,
    *,
    product_id: UUID,
    active_revision_id: UUID,
    expected_active_revision_version: int,
) -> ActiveRevisionRevalidationEligibility:
    """Project exact all-mapping recovery authority without changing durable state."""
    product = session.get(Product, product_id)
    if (
        product is None
        or product.deleted_at is not None
        or product.active_revision_id != active_revision_id
    ):
        raise PreviewJobNotFound("active revision revalidation unavailable")
    revision = session.execute(
        select(ProductRevision).where(
            ProductRevision.id == active_revision_id,
            ProductRevision.product_id == product_id,
        )
    ).scalar_one_or_none()
    if (
        revision is None
        or not revision.is_published
        or revision.version != expected_active_revision_version
    ):
        raise PreviewJobConflict("active revision revalidation conflict")
    mappings = tuple(
        session.execute(
            select(ProductRepositoryMapping)
            .options(
                selectinload(ProductRepositoryMapping.sides),
                selectinload(ProductRepositoryMapping.allowed_targets),
            )
            .where(ProductRepositoryMapping.revision_id == revision.id)
            .order_by(ProductRepositoryMapping.id)
        ).scalars()
    )
    global_blockers: list[str] = []
    if product.is_active:
        global_blockers.append("product_active")
    if product.candidate_revision_id is not None:
        global_blockers.append("candidate_revision_present")
    if not mappings:
        global_blockers.append("mappings_required")
    mapping_results: list[ActiveRevisionMappingEligibility] = []
    for mapping in mappings:
        blockers: list[str] = []
        roles = tuple(side.role for side in mapping.sides)
        if (
            (mapping.topology == "direct" and roles != ("direct",))
            or (
                mapping.topology == "separate"
                and (
                    roles != ("keys", "translations")
                    or mapping.sides[0].repository_id == mapping.sides[1].repository_id
                )
            )
            or mapping.topology not in {"direct", "separate"}
        ):
            blockers.append("mapping_configuration_invalid")
        if mapping.selected_layout_candidate_id is None or mapping.selected_layout_version is None:
            blockers.append("layout_required")
        if not blockers and not is_current_preview_confirmation(session, revision, mapping):
            blockers.append("revalidation_confirmation_required")
        mapping_results.append(
            ActiveRevisionMappingEligibility(
                mapping_id=mapping.id,
                is_current=not blockers,
                blocker_codes=tuple(blockers),
            )
        )
    combined_blockers = tuple(
        dict.fromkeys(
            [
                *global_blockers,
                *(
                    blocker
                    for mapping_result in mapping_results
                    for blocker in mapping_result.blocker_codes
                ),
            ]
        )
    )
    return ActiveRevisionRevalidationEligibility(
        product_id=product_id,
        active_revision_id=revision.id,
        active_revision_version=revision.version,
        eligible=not combined_blockers,
        blocker_codes=combined_blockers,
        mappings=tuple(mapping_results),
    )


def _mapping_has_complete_confirmation(mapping: ProductRepositoryMapping) -> bool:
    return not (
        mapping.confirmed_preview_job_id is None
        or mapping.confirmed_preview_digest is None
        or mapping.preview_confirmed_by is None
        or mapping.preview_confirmed_at is None
        or mapping.selected_layout_candidate_id is None
        or mapping.selected_layout_version is None
        or mapping.base_language is None
    )


def _mapping_has_any_confirmation(mapping: ProductRepositoryMapping) -> bool:
    return any(
        value is not None
        for value in (
            mapping.confirmed_preview_job_id,
            mapping.confirmed_preview_digest,
            mapping.preview_confirmed_by,
            mapping.preview_confirmed_at,
        )
    )


def _confirmation_job_matches(
    row: PreviewJob,
    revision: ProductRevision,
    mapping: ProductRepositoryMapping,
) -> bool:
    return (
        mapping.revision_id == revision.id
        and row.revision_scope == "candidate"
        and row.state == "succeeded"
        and row.result is not None
        and row.product_id == revision.product_id
        and row.candidate_revision_id == revision.id
        and row.candidate_revision_version == revision.version
        and row.mapping_id == mapping.id
    )


def _confirmation_job_is_latest(session: Session, row: PreviewJob) -> bool:
    latest_attempt = session.scalar(
        select(func.max(PreviewJob.attempt)).where(
            PreviewJob.input_digest == row.input_digest,
            PreviewJob.revision_scope == row.revision_scope,
        )
    )
    latest_mapping_job_id = session.scalar(
        select(PreviewJob.id)
        .where(
            PreviewJob.mapping_id == row.mapping_id,
            PreviewJob.candidate_revision_id == row.candidate_revision_id,
            PreviewJob.revision_scope == row.revision_scope,
        )
        .order_by(PreviewJob.created_at.desc(), PreviewJob.id.desc())
        .limit(1)
    )
    return latest_attempt == row.attempt and latest_mapping_job_id == row.id


def _confirmed_layout_matches(
    row: PreviewJob,
    mapping: ProductRepositoryMapping,
) -> bool:
    assert row.result is not None
    assert mapping.confirmed_preview_digest is not None
    assert mapping.selected_layout_candidate_id is not None
    assert mapping.selected_layout_version is not None
    try:
        result = _closed_result(_identity(row), row.result)
    except PreviewJobConflict, ValueError:
        return False
    assert mapping.base_language is not None
    candidates = cast(list[dict[str, object]], result["layout_candidates"])
    if not _confirmation_digest_matches(
        _identity(row),
        candidates,
        base_language=mapping.base_language,
        expected_digest=mapping.confirmed_preview_digest,
    ):
        return False
    return _selected_layout_matches(candidates, mapping)


def _selected_layout_matches(
    candidates: list[dict[str, object]],
    mapping: ProductRepositoryMapping,
) -> bool:
    assert mapping.selected_layout_candidate_id is not None
    assert mapping.selected_layout_version is not None
    if mapping.base_language is None:
        return False
    matches = [
        candidate
        for candidate in candidates
        if candidate["id"] == str(mapping.selected_layout_candidate_id)
        and candidate["version"] == mapping.selected_layout_version
    ]
    expected_side = "direct" if mapping.topology == "direct" else "translations"
    return (
        len(matches) == 1
        and matches[0]["repository_side"] == expected_side
        and _candidate_has_base_language(matches[0], mapping.base_language)
    )


def _current_failure_code(
    session: Session,
    row: PreviewJob,
    *,
    for_update: bool,
) -> PreviewJobErrorCode | None:
    revision = _current_revision(session, row, for_update=for_update)
    if revision is None:
        return "stale_candidate"
    connection = _current_connection(session, row, for_update=for_update)
    if connection is None:
        return "stale_connection"
    latest_attempt = session.scalar(
        select(func.max(PreviewJob.attempt)).where(
            PreviewJob.input_digest == row.input_digest,
            PreviewJob.revision_scope == row.revision_scope,
        )
    )
    if latest_attempt != row.attempt:
        return "stale_attempt"
    latest_mapping_job_id = session.scalar(
        select(PreviewJob.id)
        .where(
            PreviewJob.mapping_id == row.mapping_id,
            PreviewJob.candidate_revision_id == row.candidate_revision_id,
            PreviewJob.revision_scope == row.revision_scope,
        )
        .order_by(PreviewJob.created_at.desc(), PreviewJob.id.desc())
        .limit(1)
    )
    if latest_mapping_job_id != row.id:
        return "stale_identity"
    mapping = _current_mapping(session, row, for_update=for_update)
    if mapping is None or not _current_identity_matches(row, revision, mapping, connection):
        return "stale_identity"
    return None


def _current_revision(
    session: Session,
    row: PreviewJob,
    *,
    for_update: bool,
) -> ProductRevision | None:
    product_statement = select(Product).where(Product.id == row.product_id)
    if for_update:
        product_statement = product_statement.with_for_update()
    product = session.execute(product_statement).scalar_one_or_none()
    if product is None or product.deleted_at is not None:
        return None
    if row.revision_scope == "candidate":
        pointer_is_current = product.candidate_revision_id == row.candidate_revision_id
    elif row.revision_scope == "active_revalidation":
        pointer_is_current = (
            not product.is_active
            and product.candidate_revision_id is None
            and product.active_revision_id == row.candidate_revision_id
        )
    else:
        return None
    if not pointer_is_current:
        return None
    revision_statement = select(ProductRevision).where(
        ProductRevision.id == row.candidate_revision_id
    )
    if for_update:
        revision_statement = revision_statement.with_for_update()
    revision = session.execute(revision_statement).scalar_one_or_none()
    if revision is None or revision.version != row.candidate_revision_version:
        return None
    if row.revision_scope == "candidate" and revision.is_published:
        return None
    if row.revision_scope == "active_revalidation" and not revision.is_published:
        return None
    return revision


def _current_connection(
    session: Session,
    row: PreviewJob,
    *,
    for_update: bool,
) -> BitbucketConnection | PublicReadAuthority | None:
    mapping = _current_mapping(session, row, for_update=for_update)
    if is_public_github_mapping(session, mapping):
        return PublicReadAuthority() if row.connection_generation == 0 else None
    connection_statement = select(BitbucketConnection).where(BitbucketConnection.id == 1)
    if for_update:
        connection_statement = connection_statement.with_for_update()
    connection = session.execute(connection_statement).scalar_one_or_none()
    if (
        connection is None
        or connection.generation != row.connection_generation
        or connection.access_token_ciphertext is None
        or connection.refresh_token_ciphertext is not None
        or connection.scope_profile != PULLREQUEST_WRITE_SCOPE
        or connection.provider_expires_at is None
        or connection.provider_expires_at <= datetime.now(UTC)
        or connection.revoked_at is not None
    ):
        return None
    return connection


def _current_mapping(
    session: Session,
    row: PreviewJob,
    *,
    for_update: bool,
) -> ProductRepositoryMapping | None:
    mapping_statement = (
        select(ProductRepositoryMapping)
        .options(selectinload(ProductRepositoryMapping.sides))
        .where(
            ProductRepositoryMapping.id == row.mapping_id,
            ProductRepositoryMapping.revision_id == row.candidate_revision_id,
        )
    )
    if for_update:
        mapping_statement = mapping_statement.with_for_update()
    return session.execute(mapping_statement).scalar_one_or_none()


def _current_identity_matches(
    row: PreviewJob,
    revision: ProductRevision,
    mapping: ProductRepositoryMapping,
    connection: BitbucketConnection | PublicReadAuthority,
) -> bool:
    try:
        persisted_sides = _repository_sides(row)
        commits = {side.role: side.commit_hash for side in persisted_sides}
        current_sides = _complete_sides(mapping, commits)
        if row.revision_scope == "candidate":
            _encoded, current_digest = _canonical_identity(
                product_id=row.product_id,
                revision=revision,
                mapping=mapping,
                connection_generation=connection.generation,
                repository_sides=current_sides,
            )
        elif row.revision_scope == "active_revalidation":
            _encoded, current_digest = _active_revalidation_identity(
                product_id=row.product_id,
                revision=revision,
                mapping=mapping,
                connection_generation=connection.generation,
                repository_sides=current_sides,
            )
        else:
            return False
    except PreviewJobConflict:
        return False
    return (
        row.topology == mapping.topology
        and row.detector_version == PREVIEW_DETECTOR_VERSION
        and row.layout_identity == PREVIEW_LAYOUT_IDENTITY
        and row.repository_sides == current_sides
        and row.input_digest == current_digest
    )


def _start_preview_job(
    factory: sessionmaker[Session],
    *,
    job_id: UUID,
) -> PreviewJobIdentity | None:
    with factory.begin() as session:
        row = session.execute(
            select(PreviewJob).where(PreviewJob.id == job_id).with_for_update()
        ).scalar_one_or_none()
        if row is None or row.state != "queued":
            return None
        failure_code = _current_failure_code(session, row, for_update=True)
        now = datetime.now(UTC)
        if failure_code is not None:
            row.state = "failed"
            row.error_code = failure_code
            row.finished_at = now
            row.updated_at = now
            return None
        row.state = "running"
        row.started_at = now
        row.updated_at = now
        session.flush()
        return _identity(row)


def _finish_preview_job(
    factory: sessionmaker[Session],
    *,
    identity: PreviewJobIdentity,
    state: Literal["succeeded", "failed", "timed_out"],
    result: dict[str, object] | None = None,
    error_code: str | None = None,
    diagnostic_code: PreviewDiagnosticCode | None = None,
) -> None:
    with factory.begin() as session:
        row = session.execute(
            select(PreviewJob).where(PreviewJob.id == identity.job_id).with_for_update()
        ).scalar_one_or_none()
        if row is None or row.state != "running" or not _matches_started_identity(row, identity):
            return
        failure_code = _current_failure_code(session, row, for_update=True)
        now = datetime.now(UTC)
        if failure_code is not None:
            row.state = "failed"
            row.result = None
            row.error_code = failure_code
            row.diagnostic_code = None
        else:
            row.state = state
            row.result = (
                _closed_result(identity, result)
                if state == "succeeded" and result is not None
                else None
            )
            row.error_code = error_code
            row.diagnostic_code = diagnostic_code if state == "failed" else None
        row.finished_at = now
        row.updated_at = now


def execute_preview_job(
    factory: sessionmaker[Session],
    *,
    job_id: UUID,
    processor: PreviewProcessor,
) -> None:
    """Run one current attempt and persist a bounded conditional terminal state."""
    identity = _start_preview_job(factory, job_id=job_id)
    if identity is None:
        return
    try:
        raw_result = processor(identity)
        result = _closed_result(identity, raw_result)
        encoded = json.dumps(
            result,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        if len(encoded) > MAX_RESULT_BYTES:
            raise ValueError("preview result rejected")
    except PreviewJobTimedOut:
        _finish_preview_job(
            factory,
            identity=identity,
            state="timed_out",
            error_code="time_limit_exceeded",
        )
    except BitbucketProviderReadError as error:
        _finish_preview_job(
            factory,
            identity=identity,
            state="failed",
            error_code="processing_failed",
            diagnostic_code=(
                "repository_scan_limit_reached" if error.kind == "limit_exceeded" else None
            ),
        )
    except Exception:
        _finish_preview_job(
            factory,
            identity=identity,
            state="failed",
            error_code="processing_failed",
        )
    else:
        _finish_preview_job(
            factory,
            identity=identity,
            state="succeeded",
            result=result,
        )


def skeleton_preview_processor(identity: PreviewJobIdentity) -> Mapping[str, object]:
    """Return the deterministic noncanonical skeleton extended by Plan 02-12."""
    return {
        "detector_version": identity.detector_version,
        "digest": identity.input_digest,
        "layout_candidates": [],
    }
