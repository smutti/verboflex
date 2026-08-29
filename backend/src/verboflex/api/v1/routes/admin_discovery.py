"""Administrator-only live repository discovery routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal, require_roles
from verboflex.db.session import get_db_session
from verboflex.integrations.bitbucket.client import (
    BitbucketHttpAdapter,
    BitbucketProviderReadError,
)
from verboflex.schemas.admin_discovery import (
    AdminBranchListResponse,
    AdminBranchResponse,
    AdminDiscoveryErrorResponse,
    AdminSourceDiscoveryResponse,
    AdminSourceFileResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import RoleName
from verboflex.services.repositories import RepositoryNotFound
from verboflex.services.repository_discovery import (
    InvalidBranchCursor,
    discover_live_repository_sources,
    list_live_repository_branches,
    resolve_configured_repository_branch,
)

router = APIRouter(prefix="/admin/repositories", tags=["admin-discovery"])
AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]
AdminSession = Annotated[Session, Depends(get_db_session, use_cache=False)]


def get_bitbucket_discovery_adapter(request: Request) -> BitbucketHttpAdapter | None:
    """Return the process-scoped adapter initialized by the application lifespan."""
    adapter = getattr(request.app.state, "bitbucket_http_adapter", None)
    return adapter if isinstance(adapter, BitbucketHttpAdapter) else None


DiscoveryAdapter = Annotated[
    BitbucketHttpAdapter | None,
    Depends(get_bitbucket_discovery_adapter),
]

AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse | AdminDiscoveryErrorResponse},
}
DISCOVERY_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse | AdminDiscoveryErrorResponse},
    status.HTTP_409_CONFLICT: {"model": AdminDiscoveryErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse | AdminDiscoveryErrorResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": AdminDiscoveryErrorResponse},
    status.HTTP_504_GATEWAY_TIMEOUT: {"model": AdminDiscoveryErrorResponse},
}

_STATUS_BY_FAILURE = {
    "disconnected": status.HTTP_409_CONFLICT,
    "reauthorization_required": status.HTTP_409_CONFLICT,
    "permission_denied": status.HTTP_403_FORBIDDEN,
    "not_found": status.HTTP_404_NOT_FOUND,
    "unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "timeout": status.HTTP_504_GATEWAY_TIMEOUT,
    "invalid_source": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "limit_exceeded": status.HTTP_422_UNPROCESSABLE_CONTENT,
}


@router.get(
    "/{repository_id}/branches",
    operation_id="list_admin_repository_branches",
    response_model=AdminBranchListResponse,
    responses=DISCOVERY_RESPONSES,
)
async def list_admin_repository_branches(
    repository_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
    adapter: DiscoveryAdapter,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> AdminBranchListResponse | JSONResponse:
    """List exact live provider branches behind an application-owned cursor."""
    if adapter is None:
        return _failure_response(BitbucketProviderReadError(kind="unavailable"))
    try:
        page = await list_live_repository_branches(
            session,
            repository_id=repository_id,
            adapter=adapter,
            limit=limit,
            cursor=cursor,
        )
    except InvalidBranchCursor as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid cursor",
        ) from error
    except RepositoryNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository unavailable",
        ) from error
    except BitbucketProviderReadError as error:
        return _failure_response(error)
    return AdminBranchListResponse(
        items=[
            AdminBranchResponse(name=branch.name, commit_hash=branch.commit_hash)
            for branch in page.items
        ],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/{repository_id}/branch",
    operation_id="get_admin_repository_branch",
    response_model=AdminBranchResponse,
    responses=DISCOVERY_RESPONSES,
)
async def get_admin_repository_branch(
    repository_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
    adapter: DiscoveryAdapter,
    branch_name: Annotated[str, Query(min_length=1, max_length=255)],
) -> AdminBranchResponse | JSONResponse:
    """Resolve one opaque configured branch through the exact provider detail read."""
    if adapter is None:
        return _failure_response(BitbucketProviderReadError(kind="unavailable"))
    try:
        branch = await resolve_configured_repository_branch(
            session,
            repository_id=repository_id,
            branch_name=branch_name,
            adapter=adapter,
        )
    except RepositoryNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository unavailable",
        ) from error
    except BitbucketProviderReadError as error:
        return _failure_response(error)
    return AdminBranchResponse(name=branch.name, commit_hash=branch.commit_hash)


@router.get(
    "/{repository_id}/sources",
    operation_id="discover_admin_repository_sources",
    response_model=AdminSourceDiscoveryResponse,
    responses=DISCOVERY_RESPONSES,
)
async def discover_admin_repository_sources(
    repository_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
    adapter: DiscoveryAdapter,
    branch: Annotated[str, Query(min_length=1, max_length=255)],
) -> AdminSourceDiscoveryResponse | JSONResponse:
    """Return commit-bound candidate metadata while keeping raw bytes backend-only."""
    if adapter is None:
        return _failure_response(BitbucketProviderReadError(kind="unavailable"))
    try:
        snapshot = await discover_live_repository_sources(
            session,
            repository_id=repository_id,
            branch=branch,
            adapter=adapter,
        )
    except RepositoryNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository unavailable",
        ) from error
    except BitbucketProviderReadError as error:
        return _failure_response(error)
    return AdminSourceDiscoveryResponse(
        commit_hash=snapshot.commit_hash,
        files=[
            AdminSourceFileResponse(path=file.path, size=len(file.content))
            for file in snapshot.files
        ],
        total_bytes=snapshot.total_bytes,
    )


def _failure_response(error: BitbucketProviderReadError) -> JSONResponse:
    body = AdminDiscoveryErrorResponse(
        detail="Bitbucket discovery unavailable",
        state=error.kind,
    )
    return JSONResponse(
        status_code=_STATUS_BY_FAILURE[error.kind],
        content=body.model_dump(mode="json"),
    )
