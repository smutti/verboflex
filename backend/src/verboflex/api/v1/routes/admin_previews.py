"""Administrator-only durable preview job resources."""

from typing import Annotated, Any, NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal, require_roles
from verboflex.db.session import get_db_session
from verboflex.schemas.previews import (
    AdminActiveRevisionRevalidationConfirmationRequest,
    AdminActiveRevisionRevalidationConfirmationResponse,
    AdminActiveRevisionRevalidationJobCreateRequest,
    AdminActiveRevisionRevalidationJobResponse,
    AdminPreviewConfirmationRequest,
    AdminPreviewConfirmationResponse,
    AdminPreviewJobCreateRequest,
    AdminPreviewJobResponse,
    AdminPreviewJobResultResponse,
    AdminPreviewRepositorySideResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import RoleName
from verboflex.services.preview_jobs import (
    ActiveRevisionRevalidationConfirmationRecord,
    PreviewConnectionUnavailable,
    PreviewEnqueuer,
    PreviewJobConflict,
    PreviewJobNotFound,
    PreviewJobRecord,
    confirm_active_revision_revalidation,
    confirm_preview_job,
    create_or_reuse_active_revision_revalidation_job,
    create_or_reuse_preview_job,
    enqueue_preview_job,
    get_preview_job,
)
from verboflex.services.preview_jobs import (
    get_active_revision_revalidation_job as get_active_revision_revalidation_job_record,
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


def _active_response(
    record: PreviewJobRecord,
) -> AdminActiveRevisionRevalidationJobResponse:
    """Rename the internal compatibility fields at the active-revision boundary."""
    return AdminActiveRevisionRevalidationJobResponse(
        id=record.id,
        input_digest=record.input_digest,
        attempt=record.attempt,
        state=record.state,
        product_id=record.product_id,
        active_revision_id=record.candidate_revision_id,
        active_revision_version=record.candidate_revision_version,
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
        error_code=(
            "stale_active_revision" if record.error_code == "stale_candidate" else record.error_code
        ),
        is_current=record.is_current,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


def _active_confirmation_response(
    confirmation: ActiveRevisionRevalidationConfirmationRecord,
    *,
    record: PreviewJobRecord,
) -> AdminActiveRevisionRevalidationConfirmationResponse:
    return AdminActiveRevisionRevalidationConfirmationResponse(
        job_id=confirmation.job_id,
        product_id=confirmation.product_id,
        active_revision_id=confirmation.revision_id,
        active_revision_version=confirmation.revision_version,
        mapping_id=confirmation.mapping_id,
        connection_generation=confirmation.connection_generation,
        commits=[
            AdminPreviewRepositorySideResponse(
                role=side.role,
                repository_id=side.repository_id,
                source_branch=side.source_branch,
                commit_hash=side.commit_hash,
            )
            for side in record.repository_sides
        ],
        preview_digest=confirmation.preview_digest,
        layout_candidate_id=confirmation.layout_candidate_id,
        layout_candidate_version=confirmation.layout_candidate_version,
        confirmed_by=confirmation.confirmed_by,
        confirmed_at=confirmation.confirmed_at,
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


def _raise_active_revalidation_error(
    error: PreviewJobNotFound | PreviewJobConflict | PreviewConnectionUnavailable,
) -> NoReturn:
    if isinstance(error, PreviewJobNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active revision revalidation unavailable",
        ) from error
    if isinstance(error, PreviewJobConflict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Active revision revalidation conflict",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Active revision revalidation unavailable",
    ) from error


def _active_confirmation_identity_matches(
    payload: AdminActiveRevisionRevalidationConfirmationRequest,
    record: PreviewJobRecord,
) -> bool:
    commits = {commit.role: commit.commit_hash.lower() for commit in payload.commits}
    if len(commits) != len(payload.commits):
        return False
    return (
        payload.active_revision_id == record.candidate_revision_id
        and payload.active_revision_version == record.candidate_revision_version
        and payload.mapping_id == record.mapping_id
        and payload.connection_generation == record.connection_generation
        and commits == {side.role: side.commit_hash for side in record.repository_sides}
    )


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


@router.post(
    "/admin/preview-jobs/{job_id}/confirmation",
    operation_id="confirm_admin_preview_job",
    response_model=AdminPreviewConfirmationResponse,
    responses=RESPONSES,
)
async def confirm_admin_preview_job(
    job_id: UUID,
    payload: AdminPreviewConfirmationRequest,
    principal: AdminPrincipal,
    session: AdminSession,
) -> AdminPreviewConfirmationResponse:
    """Bind one current exact candidate to its mapping and confirming administrator."""
    try:
        confirmation = confirm_preview_job(
            session,
            job_id=job_id,
            preview_digest=payload.preview_digest,
            layout_candidate_id=payload.layout_candidate_id,
            layout_candidate_version=payload.layout_candidate_version,
            actor_id=principal.user_id,
        )
    except (PreviewJobNotFound, PreviewJobConflict) as error:
        _raise_preview_error(error)
    return AdminPreviewConfirmationResponse(
        job_id=confirmation.job_id,
        mapping_id=confirmation.mapping_id,
        preview_digest=confirmation.preview_digest,
        layout_candidate_id=confirmation.layout_candidate_id,
        layout_candidate_version=confirmation.layout_candidate_version,
        confirmed_by=confirmation.confirmed_by,
        confirmed_at=confirmation.confirmed_at,
    )


@router.post(
    (
        "/admin/products/{product_id}/revisions/{revision_id}/mappings/{mapping_id}"
        "/revalidation-preview-jobs"
    ),
    operation_id="create_admin_active_revision_revalidation_job",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AdminActiveRevisionRevalidationJobResponse,
    responses=RESPONSES,
)
async def create_admin_active_revision_revalidation_job(
    product_id: UUID,
    revision_id: UUID,
    mapping_id: UUID,
    payload: AdminActiveRevisionRevalidationJobCreateRequest,
    _principal: AdminPrincipal,
    session: AdminSession,
    enqueuer: PreviewEnqueueDependency,
) -> AdminActiveRevisionRevalidationJobResponse:
    """Create or reuse read-only work for one exact inactive published mapping."""
    commits = {commit.role: commit.commit_hash for commit in payload.commits}
    if len(commits) != len(payload.commits):
        _raise_active_revalidation_error(PreviewJobConflict("duplicate commit role"))
    try:
        record = create_or_reuse_active_revision_revalidation_job(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            mapping_id=mapping_id,
            expected_active_revision_version=payload.expected_active_revision_version,
            commits=commits,
            enqueuer=enqueuer,
        )
    except (PreviewJobNotFound, PreviewJobConflict, PreviewConnectionUnavailable) as error:
        _raise_active_revalidation_error(error)
    return _active_response(record)


@router.get(
    "/admin/active-revision-revalidation-jobs/{job_id}",
    operation_id="get_admin_active_revision_revalidation_job",
    response_model=AdminActiveRevisionRevalidationJobResponse,
    responses=RESPONSES,
)
async def get_admin_active_revision_revalidation_job(
    job_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminActiveRevisionRevalidationJobResponse:
    """Inspect bounded active-revision work without consulting provider state."""
    try:
        record = get_active_revision_revalidation_job_record(session, job_id=job_id)
    except (PreviewJobNotFound, PreviewJobConflict) as error:
        _raise_active_revalidation_error(error)
    return _active_response(record)


@router.post(
    "/admin/active-revision-revalidation-jobs/{job_id}/confirmation",
    operation_id="confirm_admin_active_revision_revalidation",
    response_model=AdminActiveRevisionRevalidationConfirmationResponse,
    responses=RESPONSES,
)
async def confirm_admin_active_revision_revalidation(
    job_id: UUID,
    payload: AdminActiveRevisionRevalidationConfirmationRequest,
    principal: AdminPrincipal,
    session: AdminSession,
) -> AdminActiveRevisionRevalidationConfirmationResponse:
    """Confirm only when caller and live authority share one complete identity."""
    try:
        record = get_active_revision_revalidation_job_record(session, job_id=job_id)
        if not _active_confirmation_identity_matches(payload, record):
            raise PreviewJobConflict("active revalidation identity conflict")
        confirmation = confirm_active_revision_revalidation(
            session,
            job_id=job_id,
            preview_digest=payload.preview_digest,
            layout_candidate_id=payload.layout_candidate_id,
            layout_candidate_version=payload.layout_candidate_version,
            actor_id=principal.user_id,
        )
    except (PreviewJobNotFound, PreviewJobConflict) as error:
        _raise_active_revalidation_error(error)
    return _active_confirmation_response(confirmation, record=record)
