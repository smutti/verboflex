"""Administrator-only direct candidate mapping routes."""

from typing import Annotated, Any, NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from verboflex.api.v1.routes.admin_discovery import get_bitbucket_discovery_adapter
from verboflex.auth.principal import Principal, require_roles
from verboflex.db.session import get_db_session
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.schemas.admin_mappings import (
    AdminDirectMappingWriteRequest,
    AdminMappingConflictResponse,
    AdminMappingListResponse,
    AdminMappingResponse,
    AdminMappingWriteRequest,
)
from verboflex.schemas.imports import (
    AdminImportBaselineResponse,
    AdminImportRepositorySideResponse,
    AdminImportSourceReferenceResponse,
    AdminPublishedMappingImportListResponse,
    AdminPublishedMappingImportResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import RoleName
from verboflex.services.import_jobs import (
    ImportConflict,
    ImportConnectionUnavailable,
    ImportEnqueuer,
    ImportJobRecord,
    ImportNotFound,
    create_or_start_import,
    enqueue_import_job,
    get_import_job,
    list_published_mapping_imports,
)
from verboflex.services.mappings import (
    InvalidMappingCursor,
    InvalidMappingInput,
    MappingBranchConflict,
    MappingConflict,
    MappingNotFound,
    MappingRecord,
    MappingSideInput,
    MappingTargetConflict,
    MappingVersionConflict,
    create_direct_mapping,
    create_separate_mapping,
    list_candidate_mappings,
    list_revision_mappings,
    update_direct_mapping,
    update_separate_mapping,
)

router = APIRouter(
    prefix="/admin/products/{product_id}",
    tags=["admin-mappings"],
)
AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]
AdminSession = Annotated[Session, Depends(get_db_session, use_cache=False)]
DiscoveryAdapter = Annotated[
    BitbucketHttpAdapter | None,
    Depends(get_bitbucket_discovery_adapter),
]

AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
}
COLLECTION_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
MUTATION_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": AdminMappingConflictResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
}
IMPORT_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
}


def get_import_job_enqueuer(request: Request) -> ImportEnqueuer:
    """Return the overridable UUID-only queue seam."""
    candidate = getattr(request.app.state, "import_job_enqueuer", None)
    if candidate is None:
        return enqueue_import_job
    if not callable(candidate):
        raise RuntimeError("import job enqueuer unavailable")
    return cast(ImportEnqueuer, candidate)


ImportEnqueueDependency = Annotated[ImportEnqueuer, Depends(get_import_job_enqueuer)]


def _response(record: MappingRecord) -> AdminMappingResponse:
    return AdminMappingResponse(
        id=record.id,
        topology=record.topology,
        primary_repository_id=record.primary_repository_id,
        primary_source_branch=record.primary_source_branch,
        translations_repository_id=record.translations_repository_id,
        translations_source_branch=record.translations_source_branch,
        allowed_target_branches=list(record.allowed_target_branches),
        default_target_branch=record.default_target_branch,
        selected_layout_candidate_id=record.selected_layout_candidate_id,
        selected_layout_version=record.selected_layout_version,
        candidate_version=record.candidate_version,
    )


def _import_response(record: ImportJobRecord) -> AdminPublishedMappingImportResponse:
    return AdminPublishedMappingImportResponse(
        id=record.id,
        mapping_id=record.mapping_id,
        active_revision_id=record.active_revision_id,
        topology=record.topology,
        repository_sides=[
            AdminImportRepositorySideResponse(
                role=side.role,
                repository_id=side.repository_id,
                source_branch=side.source_branch,
            )
            for side in record.repository_sides
        ],
        state=record.state,
        active_baseline=(
            AdminImportBaselineResponse(
                imported_at=record.active_baseline.imported_at,
                source_references=[
                    AdminImportSourceReferenceResponse(
                        position=reference.position,
                        repository_side=reference.repository_side,
                        repository_id=reference.repository_id,
                        source_branch=reference.source_branch,
                        commit_hash=reference.commit_hash,
                        path=reference.path,
                        size_bytes=reference.size_bytes,
                        sha256=reference.sha256,
                    )
                    for reference in record.active_baseline.source_references
                ],
            )
            if record.active_baseline is not None
            else None
        ),
        latest_execution_at=record.latest_execution_at,
        retry_count=record.retry_count,
        error_category=record.error_category,
        error_message=record.error_message,
    )


def _raise_import_error(
    error: ImportNotFound | ImportConflict | ImportConnectionUnavailable,
) -> NoReturn:
    if isinstance(error, ImportNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published import unavailable",
        ) from error
    if isinstance(error, ImportConflict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Published import conflict",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Published import connection unavailable",
    ) from error


@router.get(
    "/published/mapping-imports",
    operation_id="list_admin_published_mapping_imports",
    response_model=AdminPublishedMappingImportListResponse,
    responses=IMPORT_RESPONSES,
)
async def list_admin_published_mapping_imports(
    product_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminPublishedMappingImportListResponse:
    """List direct mappings from the exact active published revision."""
    try:
        records = list_published_mapping_imports(session, product_id=product_id)
    except ImportNotFound as error:
        _raise_import_error(error)
    return AdminPublishedMappingImportListResponse(
        items=[_import_response(record) for record in records]
    )


@router.post(
    "/published/mappings/{mapping_id}/imports",
    operation_id="start_admin_published_mapping_import",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AdminPublishedMappingImportResponse,
    responses=IMPORT_RESPONSES,
)
async def start_admin_published_mapping_import(
    product_id: UUID,
    mapping_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
    enqueuer: ImportEnqueueDependency,
) -> AdminPublishedMappingImportResponse:
    """Persist one queued logical import before dispatching its UUID."""
    try:
        record = create_or_start_import(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            enqueuer=enqueuer,
        )
    except (ImportNotFound, ImportConflict, ImportConnectionUnavailable) as error:
        _raise_import_error(error)
    return _import_response(record)


@router.get(
    "/imports/{import_id}",
    operation_id="get_admin_import",
    response_model=AdminPublishedMappingImportResponse,
    responses=IMPORT_RESPONSES,
)
async def get_admin_import(
    product_id: UUID,
    import_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminPublishedMappingImportResponse:
    """Read one logical import from PostgreSQL without Celery state."""
    try:
        record = get_import_job(
            session,
            product_id=product_id,
            import_id=import_id,
        )
    except ImportNotFound as error:
        _raise_import_error(error)
    return _import_response(record)


def _conflict(detail: str, field: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": detail, "field": field},
    )


def _raise_mapping_error(error: Exception) -> NoReturn:
    if isinstance(error, MappingNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mapping candidate unavailable",
        ) from error
    if isinstance(error, InvalidMappingInput):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid mapping input",
        ) from error
    raise error


MappingMutationError = (
    MappingConflict
    | MappingVersionConflict
    | MappingBranchConflict
    | MappingTargetConflict
    | MappingNotFound
    | InvalidMappingInput
)


def _mutation_error_response(error: MappingMutationError) -> JSONResponse:
    """Project one domain failure into the bounded form-addressable contract."""
    if isinstance(error, MappingConflict):
        return _conflict("Mapping unavailable", "mapping_identity")
    if isinstance(error, MappingVersionConflict):
        return _conflict("Mapping candidate conflict", "candidate_version")
    if isinstance(error, MappingBranchConflict):
        return _conflict("Source branch unavailable", error.field)
    if isinstance(error, MappingTargetConflict):
        return _conflict("Target branch unavailable", "allowed_target_branches")
    _raise_mapping_error(error)


@router.get(
    "/candidate/mappings",
    operation_id="list_admin_candidate_mappings",
    response_model=AdminMappingListResponse,
    responses=COLLECTION_RESPONSES,
)
async def list_admin_candidate_mappings(
    product_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> AdminMappingListResponse:
    """List one product candidate in the server-owned exact tuple order."""
    try:
        page = list_candidate_mappings(
            session,
            product_id=product_id,
            limit=limit,
            cursor=cursor,
        )
    except InvalidMappingCursor as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid cursor",
        ) from error
    except MappingNotFound as error:
        _raise_mapping_error(error)
    return AdminMappingListResponse(
        items=[_response(record) for record in page.items],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/revisions/{revision_id}/mappings",
    operation_id="list_admin_revision_mappings",
    response_model=AdminMappingListResponse,
    responses=COLLECTION_RESPONSES,
)
async def list_admin_revision_mappings(
    product_id: UUID,
    revision_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> AdminMappingListResponse:
    """List one explicitly owned active or candidate revision without mutation."""
    try:
        page = list_revision_mappings(
            session,
            product_id=product_id,
            revision_id=revision_id,
            limit=limit,
            cursor=cursor,
        )
    except InvalidMappingCursor as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid cursor",
        ) from error
    except MappingNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mapping revision unavailable",
        ) from error
    return AdminMappingListResponse(
        items=[_response(record) for record in page.items],
        next_cursor=page.next_cursor,
    )


@router.post(
    "/candidate/mappings",
    operation_id="create_admin_candidate_mapping",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminMappingResponse,
    responses=MUTATION_RESPONSES,
)
async def create_admin_candidate_mapping(
    product_id: UUID,
    payload: AdminMappingWriteRequest,
    _principal: AdminPrincipal,
    session: AdminSession,
    adapter: DiscoveryAdapter,
) -> AdminMappingResponse | JSONResponse:
    """Create one live-validated direct mapping on the current candidate."""
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mapping branch discovery unavailable",
        )
    try:
        if isinstance(payload, AdminDirectMappingWriteRequest):
            record = await create_direct_mapping(
                session,
                product_id=product_id,
                expected_candidate_version=payload.expected_candidate_version,
                repository_id=payload.repository_id,
                source_branch=payload.source_branch,
                allowed_target_branches=payload.allowed_target_branches,
                default_target_branch=payload.default_target_branch,
                adapter=adapter,
            )
        else:
            record = await create_separate_mapping(
                session,
                product_id=product_id,
                expected_candidate_version=payload.expected_candidate_version,
                repository_sides=tuple(
                    MappingSideInput(side.role, side.repository_id, side.source_branch)
                    for side in payload.sides
                ),
                allowed_target_branches=payload.allowed_target_branches,
                default_target_branch=payload.default_target_branch,
                adapter=adapter,
            )
    except (
        MappingConflict,
        MappingVersionConflict,
        MappingBranchConflict,
        MappingTargetConflict,
        MappingNotFound,
        InvalidMappingInput,
    ) as error:
        return _mutation_error_response(error)
    return _response(record)


@router.patch(
    "/candidate/mappings/{mapping_id}",
    operation_id="update_admin_candidate_mapping",
    response_model=AdminMappingResponse,
    responses=MUTATION_RESPONSES,
)
async def update_admin_candidate_mapping(
    product_id: UUID,
    mapping_id: UUID,
    payload: AdminMappingWriteRequest,
    _principal: AdminPrincipal,
    session: AdminSession,
    adapter: DiscoveryAdapter,
) -> AdminMappingResponse | JSONResponse:
    """Compare and replace one direct candidate mapping without lifecycle state."""
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mapping branch discovery unavailable",
        )
    try:
        if isinstance(payload, AdminDirectMappingWriteRequest):
            record = await update_direct_mapping(
                session,
                product_id=product_id,
                mapping_id=mapping_id,
                expected_candidate_version=payload.expected_candidate_version,
                repository_id=payload.repository_id,
                source_branch=payload.source_branch,
                allowed_target_branches=payload.allowed_target_branches,
                default_target_branch=payload.default_target_branch,
                adapter=adapter,
            )
        else:
            record = await update_separate_mapping(
                session,
                product_id=product_id,
                mapping_id=mapping_id,
                expected_candidate_version=payload.expected_candidate_version,
                repository_sides=tuple(
                    MappingSideInput(side.role, side.repository_id, side.source_branch)
                    for side in payload.sides
                ),
                allowed_target_branches=payload.allowed_target_branches,
                default_target_branch=payload.default_target_branch,
                adapter=adapter,
            )
    except (
        MappingConflict,
        MappingVersionConflict,
        MappingBranchConflict,
        MappingTargetConflict,
        MappingNotFound,
        InvalidMappingInput,
    ) as error:
        return _mutation_error_response(error)
    return _response(record)
