"""Administrator-only internal-user lifecycle routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal, require_roles
from verboflex.db.session import get_db_session
from verboflex.schemas.admin_users import (
    AdminUserCreateRequest,
    AdminUserCredentialResponse,
    AdminUserListResponse,
    AdminUserResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import RoleName
from verboflex.services.admin_users import (
    AdminUserAuthorityError,
    AdminUserConflict,
    AdminUserInputError,
    AdminUserRecord,
    InvalidAdminUserCursor,
    create_admin_user,
    list_admin_users,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])
AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]
AdminSession = Annotated[Session, Depends(get_db_session, use_cache=False)]


def _response(record: AdminUserRecord) -> AdminUserResponse:
    return AdminUserResponse(
        id=record.id,
        email=record.email,
        display_name=record.display_name,
        roles=list(record.roles),
        is_active=record.is_active,
        must_change_password=record.must_change_password,
    )


@router.get(
    "",
    operation_id="list_admin_users",
    response_model=AdminUserListResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def list_users(
    principal: AdminPrincipal,
    session: AdminSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> AdminUserListResponse:
    """List internal users in stable normalized-email and UUID order."""
    try:
        page = list_admin_users(
            session,
            actor_id=principal.user_id,
            limit=limit,
            cursor=cursor,
        )
    except AdminUserAuthorityError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from error
    except InvalidAdminUserCursor as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid cursor",
        ) from error
    return AdminUserListResponse(
        items=[_response(record) for record in page.items],
        next_cursor=page.next_cursor,
    )


@router.post(
    "",
    operation_id="create_admin_user",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminUserCredentialResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def create_user(
    payload: AdminUserCreateRequest,
    response: Response,
    principal: AdminPrincipal,
    session: AdminSession,
) -> AdminUserCredentialResponse:
    """Create one account and expose its generated temporary password once."""
    try:
        created = create_admin_user(
            session,
            actor_id=principal.user_id,
            email=payload.email,
            display_name=payload.display_name,
            roles=frozenset(payload.roles),
        )
    except AdminUserAuthorityError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from error
    except AdminUserConflict as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User could not be created",
        ) from error
    except (AdminUserInputError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid user input",
        ) from error

    response.headers["Cache-Control"] = "no-store"
    record = created.user
    return AdminUserCredentialResponse(
        id=record.id,
        email=record.email,
        display_name=record.display_name,
        roles=list(record.roles),
        is_active=record.is_active,
        must_change_password=record.must_change_password,
        temporary_password=created.temporary_password,
    )
