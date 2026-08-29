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

from verboflex.localization.preview.core import validate_layout_candidate_mappings
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.preview_job import PreviewJob
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping

PREVIEW_TASK_NAME = "verboflex.preview.run"
PREVIEW_DETECTOR_VERSION = "preview-skeleton-v1"
PREVIEW_LAYOUT_IDENTITY = "automatic-layout-discovery-v1"
PREVIEW_SOFT_TIME_LIMIT_SECONDS = 60
PREVIEW_HARD_TIME_LIMIT_SECONDS = 75
PREVIEW_WATCHDOG_BATCH_SIZE = 100
MAX_RESULT_BYTES = 1_048_576

PreviewJobState = Literal["queued", "running", "succeeded", "failed", "timed_out"]
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


class PreviewJobNotFound(LookupError):
    """Raised when the requested job or candidate mapping is unavailable."""


class PreviewJobConflict(ValueError):
    """Raised when submitted identity disagrees with current durable authority."""


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
    confirmed_by: UUID
    confirmed_at: datetime


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


@dataclass(frozen=True, slots=True)
class PreviewJobIdentity:
    """Complete immutable pre-detector identity loaded by a UUID-only worker."""

    job_id: UUID
    input_digest: str
    attempt: int
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
    product_id: UUID
    candidate_revision_id: UUID
    candidate_revision_version: int
    mapping_id: UUID
    connection_generation: int
    detector_version: str
    repository_sides: tuple[PreviewRepositorySide, ...]
    result: dict[str, object] | None
    error_code: PreviewJobErrorCode | None
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
    identity = _identity(row)
    result = None if row.result is None else _closed_result(identity, row.result)
    return PreviewJobRecord(
        id=row.id,
        input_digest=row.input_digest,
        attempt=row.attempt,
        state=cast(PreviewJobState, row.state),
        product_id=row.product_id,
        candidate_revision_id=row.candidate_revision_id,
        candidate_revision_version=row.candidate_revision_version,
        mapping_id=row.mapping_id,
        connection_generation=row.connection_generation,
        detector_version=row.detector_version,
        repository_sides=_repository_sides(row),
        result=result,
        error_code=cast(PreviewJobErrorCode | None, row.error_code),
        is_current=is_current,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _identity(row: PreviewJob) -> PreviewJobIdentity:
    if row.topology not in {"direct", "separate"}:
        raise PreviewJobConflict("persisted preview topology rejected")
    return PreviewJobIdentity(
        job_id=row.id,
        input_digest=row.input_digest,
        attempt=row.attempt,
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
            }
            for side in identity.repository_sides
        ],
        "topology": identity.topology,
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()


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


def _locked_mapping(
    session: Session,
    *,
    product_id: UUID,
    mapping_id: UUID,
    expected_candidate_version: int,
) -> tuple[ProductRevision, ProductRepositoryMapping]:
    product = session.execute(
        select(Product).where(Product.id == product_id).with_for_update()
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


def _connected_generation(session: Session) -> int:
    connection = session.execute(
        select(BitbucketConnection).where(BitbucketConnection.id == 1).with_for_update()
    ).scalar_one_or_none()
    if (
        connection is None
        or connection.access_token_ciphertext is None
        or connection.refresh_token_ciphertext is None
        or connection.scope_profile != "repository"
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

    app.send_task(
        PREVIEW_TASK_NAME,
        args=[str(job_id)],
        task_id=str(job_id),
        serializer="json",
        soft_time_limit=PREVIEW_SOFT_TIME_LIMIT_SECONDS,
        time_limit=PREVIEW_HARD_TIME_LIMIT_SECONDS,
    )


def create_or_reuse_preview_job(
    session: Session,
    *,
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
        connection_generation = _connected_generation(session)
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
        return _record(
            row,
            is_current=_current_failure_code(session, row, for_update=False) is None,
        )


def confirm_preview_job(
    session: Session,
    *,
    job_id: UUID,
    preview_digest: str,
    layout_candidate_id: UUID,
    layout_candidate_version: Literal[1],
    actor_id: UUID,
) -> PreviewConfirmationRecord:
    """Assign exactly one current succeeded candidate under durable authority locks."""
    with session.begin():
        row = session.execute(
            select(PreviewJob).where(PreviewJob.id == job_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise PreviewJobNotFound("preview job unavailable")
        if _current_failure_code(session, row, for_update=True) is not None:
            raise PreviewJobConflict("preview identity conflict")
        if row.state != "succeeded" or row.result is None:
            raise PreviewJobConflict("preview confirmation unavailable")
        result = _closed_result(_identity(row), row.result)
        if result["digest"] != preview_digest:
            raise PreviewJobConflict("preview identity conflict")
        raw_candidates = cast(list[dict[str, object]], result["layout_candidates"])
        matches = [
            candidate
            for candidate in raw_candidates
            if candidate["id"] == str(layout_candidate_id)
            and candidate["version"] == layout_candidate_version
        ]
        if len(matches) != 1:
            raise PreviewJobConflict("preview confirmation unavailable")
        mapping = _current_mapping(session, row, for_update=True)
        assert mapping is not None
        expected_side = "direct" if mapping.topology == "direct" else "translations"
        if matches[0]["repository_side"] != expected_side:
            raise PreviewJobConflict("preview confirmation unavailable")
        if (
            mapping.confirmed_preview_job_id == row.id
            and mapping.confirmed_preview_digest == preview_digest
            and mapping.selected_layout_candidate_id == layout_candidate_id
            and mapping.selected_layout_version == layout_candidate_version
            and mapping.preview_confirmed_by is not None
            and mapping.preview_confirmed_at is not None
        ):
            return PreviewConfirmationRecord(
                job_id=row.id,
                mapping_id=mapping.id,
                preview_digest=preview_digest,
                layout_candidate_id=layout_candidate_id,
                layout_candidate_version=layout_candidate_version,
                confirmed_by=mapping.preview_confirmed_by,
                confirmed_at=mapping.preview_confirmed_at,
            )
        confirmed_at = datetime.now(UTC)
        mapping.selected_layout_candidate_id = layout_candidate_id
        mapping.selected_layout_version = layout_candidate_version
        mapping.confirmed_preview_job_id = row.id
        mapping.confirmed_preview_digest = preview_digest
        mapping.preview_confirmed_by = actor_id
        mapping.preview_confirmed_at = confirmed_at
        mapping.updated_at = confirmed_at
        session.flush()
        return PreviewConfirmationRecord(
            job_id=row.id,
            mapping_id=mapping.id,
            preview_digest=preview_digest,
            layout_candidate_id=layout_candidate_id,
            layout_candidate_version=layout_candidate_version,
            confirmed_by=actor_id,
            confirmed_at=confirmed_at,
        )


def is_current_preview_confirmation(
    session: Session,
    revision: ProductRevision,
    mapping: ProductRepositoryMapping,
) -> bool:
    """Recompute one exact confirmation against current durable authority."""
    if not _mapping_has_complete_confirmation(mapping):
        return False
    assert mapping.confirmed_preview_job_id is not None
    row = session.get(PreviewJob, mapping.confirmed_preview_job_id)
    if row is None or not _confirmation_job_matches(row, revision, mapping):
        return False
    connection = _current_connection(session, row, for_update=True)
    return (
        connection is not None
        and _confirmation_job_is_latest(session, row)
        and _current_identity_matches(row, revision, mapping, connection)
        and _confirmed_layout_matches(row, mapping)
    )


def _mapping_has_complete_confirmation(mapping: ProductRepositoryMapping) -> bool:
    return not (
        mapping.confirmed_preview_job_id is None
        or mapping.confirmed_preview_digest is None
        or mapping.preview_confirmed_by is None
        or mapping.preview_confirmed_at is None
        or mapping.selected_layout_candidate_id is None
        or mapping.selected_layout_version is None
    )


def _confirmation_job_matches(
    row: PreviewJob,
    revision: ProductRevision,
    mapping: ProductRepositoryMapping,
) -> bool:
    return (
        mapping.revision_id == revision.id
        and row.state == "succeeded"
        and row.result is not None
        and row.product_id == revision.product_id
        and row.candidate_revision_id == revision.id
        and row.candidate_revision_version == revision.version
        and row.mapping_id == mapping.id
    )


def _confirmation_job_is_latest(session: Session, row: PreviewJob) -> bool:
    latest_attempt = session.scalar(
        select(func.max(PreviewJob.attempt)).where(PreviewJob.input_digest == row.input_digest)
    )
    latest_mapping_job_id = session.scalar(
        select(PreviewJob.id)
        .where(
            PreviewJob.mapping_id == row.mapping_id,
            PreviewJob.candidate_revision_id == row.candidate_revision_id,
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
    if result["digest"] != mapping.confirmed_preview_digest:
        return False
    candidates = cast(list[dict[str, object]], result["layout_candidates"])
    return _selected_layout_matches(candidates, mapping)


def _selected_layout_matches(
    candidates: list[dict[str, object]],
    mapping: ProductRepositoryMapping,
) -> bool:
    assert mapping.selected_layout_candidate_id is not None
    assert mapping.selected_layout_version is not None
    matches = [
        candidate
        for candidate in candidates
        if candidate["id"] == str(mapping.selected_layout_candidate_id)
        and candidate["version"] == mapping.selected_layout_version
    ]
    expected_side = "direct" if mapping.topology == "direct" else "translations"
    return len(matches) == 1 and matches[0]["repository_side"] == expected_side


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
        select(func.max(PreviewJob.attempt)).where(PreviewJob.input_digest == row.input_digest)
    )
    if latest_attempt != row.attempt:
        return "stale_attempt"
    latest_mapping_job_id = session.scalar(
        select(PreviewJob.id)
        .where(
            PreviewJob.mapping_id == row.mapping_id,
            PreviewJob.candidate_revision_id == row.candidate_revision_id,
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
    if product is None or product.candidate_revision_id != row.candidate_revision_id:
        return None
    revision_statement = select(ProductRevision).where(
        ProductRevision.id == row.candidate_revision_id
    )
    if for_update:
        revision_statement = revision_statement.with_for_update()
    revision = session.execute(revision_statement).scalar_one_or_none()
    if (
        revision is None
        or revision.is_published
        or revision.version != row.candidate_revision_version
    ):
        return None
    return revision


def _current_connection(
    session: Session,
    row: PreviewJob,
    *,
    for_update: bool,
) -> BitbucketConnection | None:
    connection_statement = select(BitbucketConnection).where(BitbucketConnection.id == 1)
    if for_update:
        connection_statement = connection_statement.with_for_update()
    connection = session.execute(connection_statement).scalar_one_or_none()
    if (
        connection is None
        or connection.generation != row.connection_generation
        or connection.access_token_ciphertext is None
        or connection.refresh_token_ciphertext is None
        or connection.scope_profile != "repository"
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
    connection: BitbucketConnection,
) -> bool:
    try:
        persisted_sides = _repository_sides(row)
        commits = {side.role: side.commit_hash for side in persisted_sides}
        current_sides = _complete_sides(mapping, commits)
        _encoded, current_digest = _canonical_identity(
            product_id=row.product_id,
            revision=revision,
            mapping=mapping,
            connection_generation=connection.generation,
            repository_sides=current_sides,
        )
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
        else:
            row.state = state
            row.result = (
                _closed_result(identity, result)
                if state == "succeeded" and result is not None
                else None
            )
            row.error_code = error_code
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
