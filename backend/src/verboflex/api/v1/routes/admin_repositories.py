"""Administrator-only reusable repository registry routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal, require_roles
from verboflex.db.session import get_db_session
from verboflex.schemas.admin_repositories import (
    AdminRepositoryCreateRequest,
    AdminRepositoryListResponse,
    AdminRepositoryResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import RoleName
from verboflex.services.repositories import (
    InvalidRepositoryCursor,
    RepositoryConflict,
    RepositoryNotFound,
    RepositoryRecord,
    get_repository,
    list_repositories,
    register_repository,
)

router = APIRouter(prefix="/admin/repositories", tags=["admin-repositories"])
AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]
AdminSession = Annotated[Session, Depends(get_db_session, use_cache=False)]

AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
}
COLLECTION_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
CREATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
DETAIL_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}


def _response(record: RepositoryRecord) -> AdminRepositoryResponse:
    return AdminRepositoryResponse(
        id=record.id,
        workspace=record.workspace,
        repository_slug=record.repository_slug,
        descriptive_name=record.descriptive_name,
        provider=record.provider,
    )


@router.get(
    "",
    operation_id="list_admin_repositories",
    response_model=AdminRepositoryListResponse,
    responses=COLLECTION_RESPONSES,
)
async def list_admin_repository_collection(
    _principal: AdminPrincipal,
    session: AdminSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> AdminRepositoryListResponse:
    """List repositories in stable server-owned selection order."""
    try:
        page = list_repositories(session, limit=limit, cursor=cursor)
    except InvalidRepositoryCursor as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid cursor",
        ) from error
    return AdminRepositoryListResponse(
        items=[_response(record) for record in page.items],
        next_cursor=page.next_cursor,
    )


@router.post(
    "",
    operation_id="create_admin_repository",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminRepositoryResponse,
    responses=CREATE_RESPONSES,
)
async def create_admin_repository(
    payload: AdminRepositoryCreateRequest,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminRepositoryResponse:
    """Register one normalized identity without provider discovery."""
    try:
        record = register_repository(
            session,
            workspace=payload.workspace,
            repository_slug=payload.repository_slug,
            descriptive_name=payload.descriptive_name,
            actor_id=_principal.user_id,
        )
    except RepositoryConflict as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository unavailable",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid repository input",
        ) from error
    return _response(record)


@router.get(
    "/{repository_id}",
    operation_id="get_admin_repository",
    response_model=AdminRepositoryResponse,
    responses=DETAIL_RESPONSES,
)
async def get_admin_repository_detail(
    repository_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminRepositoryResponse:
    """Return one existing UUID for a separate mapping reuse operation."""
    try:
        record = get_repository(session, repository_id=repository_id)
    except RepositoryNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository unavailable",
        ) from error
    return _response(record)
