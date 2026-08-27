"""Administrator-only direct candidate mapping routes."""

from typing import Annotated, Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import RoleName
from verboflex.services.mappings import (
    InvalidMappingCursor,
    InvalidMappingInput,
    MappingBranchConflict,
    MappingConflict,
    MappingNotFound,
    MappingRecord,
    MappingTargetConflict,
    MappingVersionConflict,
    create_direct_mapping,
    list_candidate_mappings,
    update_direct_mapping,
)

router = APIRouter(
    prefix="/admin/products/{product_id}/candidate/mappings",
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


@router.get(
    "",
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


@router.post(
    "",
    operation_id="create_admin_candidate_mapping",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminMappingResponse,
    responses=MUTATION_RESPONSES,
)
async def create_admin_candidate_mapping(
    product_id: UUID,
    payload: AdminDirectMappingWriteRequest,
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
    except MappingConflict:
        return _conflict("Mapping unavailable", "mapping_identity")
    except MappingVersionConflict:
        return _conflict("Mapping candidate conflict", "candidate_version")
    except MappingBranchConflict:
        return _conflict("Source branch unavailable", "source_branch")
    except MappingTargetConflict:
        return _conflict("Target branch unavailable", "allowed_target_branches")
    except (MappingNotFound, InvalidMappingInput) as error:
        _raise_mapping_error(error)
    return _response(record)


@router.patch(
    "/{mapping_id}",
    operation_id="update_admin_candidate_mapping",
    response_model=AdminMappingResponse,
    responses=MUTATION_RESPONSES,
)
async def update_admin_candidate_mapping(
    product_id: UUID,
    mapping_id: UUID,
    payload: AdminDirectMappingWriteRequest,
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
    except MappingConflict:
        return _conflict("Mapping unavailable", "mapping_identity")
    except MappingVersionConflict:
        return _conflict("Mapping candidate conflict", "candidate_version")
    except MappingBranchConflict:
        return _conflict("Source branch unavailable", "source_branch")
    except MappingTargetConflict:
        return _conflict("Target branch unavailable", "allowed_target_branches")
    except (MappingNotFound, InvalidMappingInput) as error:
        _raise_mapping_error(error)
    return _response(record)
