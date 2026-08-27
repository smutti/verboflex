"""Durable preview job identity, idempotency, and conditional state transitions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.preview_job import PreviewJob
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping

PREVIEW_TASK_NAME = "verboflex.preview.run"
PREVIEW_DETECTOR_VERSION = "preview-skeleton-v1"
PREVIEW_LAYOUT_IDENTITY = "automatic-layout-discovery-v1"
PREVIEW_SOFT_TIME_LIMIT_SECONDS = 60
PREVIEW_HARD_TIME_LIMIT_SECONDS = 75
MAX_RESULT_BYTES = 1_048_576

PreviewJobState = Literal["queued", "running", "succeeded", "failed", "timed_out"]
RepositoryRole = Literal["direct", "keys", "translations"]


class PreviewJobNotFound(LookupError):
    """Raised when the requested job or candidate mapping is unavailable."""


class PreviewJobConflict(ValueError):
    """Raised when submitted identity disagrees with current durable authority."""


class PreviewConnectionUnavailable(RuntimeError):
    """Raised when there is no connected repository-read credential generation."""


class PreviewJobTimedOut(TimeoutError):
    """Raised by the worker timeout adapter to request a durable timeout state."""


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
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


PreviewProcessor = Callable[[PreviewJobIdentity], Mapping[str, object]]


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


def _record(row: PreviewJob) -> PreviewJobRecord:
    if row.state not in {"queued", "running", "succeeded", "failed", "timed_out"}:
        raise PreviewJobConflict("persisted preview state rejected")
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
        result=row.result,
        error_code=row.error_code,
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
    if isinstance(raw_commits, (str, bytes)) or not isinstance(raw_commits, Mapping):
        raise PreviewJobConflict("preview commit identity rejected")
    commits: dict[str, str] = {}
    for raw_role, raw_commit in raw_commits.items():
        if raw_role not in {"direct", "keys", "translations"} or raw_role in commits:
            raise PreviewJobConflict("preview commit identity rejected")
        commits[cast(str, raw_role)] = _exact_commit_hash(raw_commit)
    persisted_sides = sorted(mapping.sides, key=lambda side: side.role)
    expected_roles = {side.role for side in persisted_sides}
    if set(commits) != expected_roles:
        raise PreviewJobConflict("preview commit identity rejected")
    if mapping.topology == "direct" and expected_roles != {"direct"}:
        raise PreviewJobConflict("preview mapping identity rejected")
    if mapping.topology == "separate" and expected_roles != {"keys", "translations"}:
        raise PreviewJobConflict("preview mapping identity rejected")
    return [
        {
            "role": side.role,
            "repository_id": str(side.repository_id),
            "source_branch": side.source_branch,
            "commit_hash": commits[side.role],
        }
        for side in persisted_sides
    ]


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
        record = _record(row)

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
            record = _record(row)
    return record


def get_preview_job(session: Session, *, job_id: UUID) -> PreviewJobRecord:
    """Read one bounded status/result from PostgreSQL, never Celery state."""
    with session.begin():
        row = session.get(PreviewJob, job_id)
        if row is None:
            raise PreviewJobNotFound("preview job unavailable")
        return _record(row)


def _current_failure_code(session: Session, row: PreviewJob) -> str | None:
    product = session.execute(
        select(Product).where(Product.id == row.product_id).with_for_update()
    ).scalar_one_or_none()
    if product is None or product.candidate_revision_id != row.candidate_revision_id:
        return "stale_candidate"
    revision = session.execute(
        select(ProductRevision)
        .where(ProductRevision.id == row.candidate_revision_id)
        .with_for_update()
    ).scalar_one_or_none()
    if (
        revision is None
        or revision.is_published
        or revision.version != row.candidate_revision_version
    ):
        return "stale_candidate"
    connection = session.execute(
        select(BitbucketConnection).where(BitbucketConnection.id == 1).with_for_update()
    ).scalar_one_or_none()
    if (
        connection is None
        or connection.generation != row.connection_generation
        or connection.access_token_ciphertext is None
        or connection.refresh_token_ciphertext is None
        or connection.scope_profile != "repository"
        or connection.revoked_at is not None
    ):
        return "stale_connection"
    latest_attempt = session.scalar(
        select(func.max(PreviewJob.attempt)).where(PreviewJob.input_digest == row.input_digest)
    )
    if latest_attempt != row.attempt:
        return "stale_attempt"
    return None


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
        failure_code = _current_failure_code(session, row)
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
        if row is None or row.state != "running" or row.attempt != identity.attempt:
            return
        failure_code = _current_failure_code(session, row)
        now = datetime.now(UTC)
        if failure_code is not None:
            row.state = "failed"
            row.result = None
            row.error_code = failure_code
        else:
            row.state = state
            row.result = result
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
        result = dict(raw_result)
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
