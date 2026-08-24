"""Bounded authenticated user contracts."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from redis import Redis

from verboflex.auth.principal import CurrentPrincipal
from verboflex.auth.rate_limits import (
    BoundedLocalRateLimiter,
    enforce_ordinary_read_rate_limit,
    get_local_rate_limiter,
    get_redis_client,
    raise_rate_limited,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import CurrentUserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    operation_id="read_current_user",
    response_model=CurrentUserResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    },
)
async def read_current_user(
    principal: CurrentPrincipal,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    local_limiter: Annotated[BoundedLocalRateLimiter, Depends(get_local_rate_limiter)],
) -> CurrentUserResponse:
    """Expose the final current-identity signature."""
    limit = enforce_ordinary_read_rate_limit(
        redis_client,
        local_limiter,
        user_id=str(principal.user_id),
    )
    if not limit.allowed:
        raise_rate_limited(limit)
    return CurrentUserResponse(
        id=principal.user_id,
        email=principal.email,
        display_name=principal.display_name,
        roles=list(principal.roles),
        must_change_password=principal.must_change_password,
    )
