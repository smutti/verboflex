"""User contract stubs."""

from fastapi import APIRouter, HTTPException, status

from verboflex.auth.principal import CurrentPrincipal
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import CurrentUserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    },
)
async def read_current_user(_principal: CurrentPrincipal) -> CurrentUserResponse:
    """Expose the final current-identity signature."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")
