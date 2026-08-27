"""Administrator-only durable preview job resources."""

from typing import Annotated, Any, NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal, require_roles
from verboflex.db.session import get_db_session
from verboflex.schemas.previews import (
    AdminPreviewJobCreateRequest,
    AdminPreviewJobResponse,
    AdminPreviewJobResultResponse,
    AdminPreviewRepositorySideResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import RoleName
from verboflex.services.preview_jobs import (
    PreviewConnectionUnavailable,
    PreviewEnqueuer,
    PreviewJobConflict,
    PreviewJobNotFound,
    PreviewJobRecord,
    create_or_reuse_preview_job,
    enqueue_preview_job,
    get_preview_job,
)

router = APIRouter(tags=["admin-previews"])
AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]
AdminSession = Annotated[Session, Depends(get_db_session, use_cache=False)]

RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
}


def get_preview_job_enqueuer(request: Request) -> PreviewEnqueuer:
    """Return an overridable UUID-only transport while defaulting to Celery."""
    candidate = getattr(request.app.state, "preview_job_enqueuer", None)
    if candidate is None:
        return enqueue_preview_job
    if not callable(candidate):
        raise RuntimeError("preview job enqueuer unavailable")
    return cast(PreviewEnqueuer, candidate)


PreviewEnqueueDependency = Annotated[PreviewEnqueuer, Depends(get_preview_job_enqueuer)]


def _response(record: PreviewJobRecord) -> AdminPreviewJobResponse:
    return AdminPreviewJobResponse(
        id=record.id,
        input_digest=record.input_digest,
        attempt=record.attempt,
        state=record.state,
        product_id=record.product_id,
        candidate_revision_id=record.candidate_revision_id,
        candidate_revision_version=record.candidate_revision_version,
        mapping_id=record.mapping_id,
        connection_generation=record.connection_generation,
        detector_version=record.detector_version,
        repository_sides=[
            AdminPreviewRepositorySideResponse(
                role=side.role,
                repository_id=side.repository_id,
                source_branch=side.source_branch,
                commit_hash=side.commit_hash,
            )
            for side in record.repository_sides
        ],
        result=(
            AdminPreviewJobResultResponse.model_validate(record.result)
            if record.result is not None
            else None
        ),
        error_code=record.error_code,
        is_current=record.is_current,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


def _raise_preview_error(error: Exception) -> NoReturn:
    if isinstance(error, PreviewJobNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview unavailable",
        ) from error
    if isinstance(error, PreviewJobConflict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preview identity conflict",
        ) from error
    if isinstance(error, PreviewConnectionUnavailable):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Preview connection unavailable",
        ) from error
    raise error


@router.post(
    "/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs",
    operation_id="create_admin_preview_job",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AdminPreviewJobResponse,
    responses=RESPONSES,
)
async def create_admin_preview_job(
    product_id: UUID,
    mapping_id: UUID,
    payload: AdminPreviewJobCreateRequest,
    _principal: AdminPrincipal,
    session: AdminSession,
    enqueuer: PreviewEnqueueDependency,
) -> AdminPreviewJobResponse:
    """Persist or reuse complete input identity before enqueueing one UUID."""
    commits = {commit.role: commit.commit_hash for commit in payload.commits}
    if len(commits) != len(payload.commits):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preview identity conflict",
        )
    try:
        record = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=payload.expected_candidate_version,
            commits=commits,
            enqueuer=enqueuer,
        )
    except (PreviewJobNotFound, PreviewJobConflict, PreviewConnectionUnavailable) as error:
        _raise_preview_error(error)
    return _response(record)


@router.get(
    "/admin/preview-jobs/{job_id}",
    operation_id="get_admin_preview_job",
    response_model=AdminPreviewJobResponse,
    responses=RESPONSES,
)
async def get_admin_preview_job(
    job_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminPreviewJobResponse:
    """Inspect one durable state/result without consulting Celery backend data."""
    try:
        record = get_preview_job(session, job_id=job_id)
    except PreviewJobNotFound as error:
        _raise_preview_error(error)
    return _response(record)
