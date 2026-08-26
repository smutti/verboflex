"""Administrator-only internal-user lifecycle routes."""

from typing import Annotated, Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal, require_roles
from verboflex.db.session import get_db_session
from verboflex.schemas.admin_users import (
    AdminUserCreateRequest,
    AdminUserCredentialResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import RoleName
from verboflex.services.admin_users import (
    AdminUserAuthorityError,
    AdminUserConflict,
    AdminUserInputError,
    AdminUserNotFound,
    AdminUserRecord,
    CreatedAdminUser,
    InvalidAdminUserCursor,
    create_admin_user,
    list_admin_users,
)
from verboflex.services.admin_users import (
    deactivate_admin_user as deactivate_admin_user_service,
)
from verboflex.services.admin_users import (
    reactivate_admin_user as reactivate_admin_user_service,
)
from verboflex.services.admin_users import (
    reset_admin_user_password as reset_admin_user_password_service,
)
from verboflex.services.admin_users import (
    update_admin_user as update_admin_user_service,
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


def _credential_response(created: CreatedAdminUser) -> AdminUserCredentialResponse:
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


def _raise_lifecycle_error(error: Exception) -> NoReturn:
    if isinstance(error, AdminUserAuthorityError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from error
    if isinstance(error, AdminUserNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User unavailable",
        ) from error
    if isinstance(error, AdminUserConflict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User lifecycle conflict",
        ) from error
    if isinstance(error, AdminUserInputError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid user input",
        ) from error
    raise error


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
    except AdminUserInputError as error:
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


LIFECYCLE_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}


@router.patch(
    "/{user_id}",
    operation_id="update_admin_user",
    response_model=AdminUserResponse,
    responses=LIFECYCLE_RESPONSES,
)
async def update_user(
    user_id: UUID,
    payload: AdminUserUpdateRequest,
    principal: AdminPrincipal,
    session: AdminSession,
) -> AdminUserResponse:
    """Update display name and additive roles through one locked authority."""
    try:
        record = update_admin_user_service(
            session,
            actor_id=principal.user_id,
            target_id=user_id,
            display_name=payload.display_name,
            roles=frozenset(payload.roles),
        )
    except (
        AdminUserAuthorityError,
        AdminUserNotFound,
        AdminUserConflict,
        AdminUserInputError,
    ) as error:
        _raise_lifecycle_error(error)
    return _response(record)


@router.post(
    "/{user_id}/reset-password",
    operation_id="reset_admin_user_password",
    response_model=AdminUserCredentialResponse,
    responses=LIFECYCLE_RESPONSES,
)
async def reset_password(
    user_id: UUID,
    response: Response,
    principal: AdminPrincipal,
    session: AdminSession,
) -> AdminUserCredentialResponse:
    """Generate one new temporary password and revoke all prior authority."""
    try:
        result = reset_admin_user_password_service(
            session,
            actor_id=principal.user_id,
            target_id=user_id,
        )
    except (
        AdminUserAuthorityError,
        AdminUserNotFound,
        AdminUserConflict,
        AdminUserInputError,
    ) as error:
        _raise_lifecycle_error(error)
    response.headers["Cache-Control"] = "no-store"
    return _credential_response(result)


@router.post(
    "/{user_id}/deactivate",
    operation_id="deactivate_admin_user",
    response_model=AdminUserResponse,
    responses=LIFECYCLE_RESPONSES,
)
async def deactivate_user(
    user_id: UUID,
    principal: AdminPrincipal,
    session: AdminSession,
) -> AdminUserResponse:
    """Deactivate one account while preserving an active administrator."""
    try:
        record = deactivate_admin_user_service(
            session,
            actor_id=principal.user_id,
            target_id=user_id,
        )
    except (
        AdminUserAuthorityError,
        AdminUserNotFound,
        AdminUserConflict,
        AdminUserInputError,
    ) as error:
        _raise_lifecycle_error(error)
    return _response(record)


@router.post(
    "/{user_id}/reactivate",
    operation_id="reactivate_admin_user",
    response_model=AdminUserCredentialResponse,
    responses=LIFECYCLE_RESPONSES,
)
async def reactivate_user(
    user_id: UUID,
    response: Response,
    principal: AdminPrincipal,
    session: AdminSession,
) -> AdminUserCredentialResponse:
    """Reactivate one account with a fresh temporary password."""
    try:
        result = reactivate_admin_user_service(
            session,
            actor_id=principal.user_id,
            target_id=user_id,
        )
    except (
        AdminUserAuthorityError,
        AdminUserNotFound,
        AdminUserConflict,
        AdminUserInputError,
    ) as error:
        _raise_lifecycle_error(error)
    response.headers["Cache-Control"] = "no-store"
    return _credential_response(result)
