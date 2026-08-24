"""System-status contract stub."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from redis import Redis

from verboflex.auth.principal import CurrentPrincipal
from verboflex.auth.rate_limits import (
    ORDINARY_READ_LIMIT,
    enforce_auth_action_rate_limit,
    get_redis_client,
    raise_rate_limited,
)
from verboflex.schemas.system import ErrorResponse, SystemStatusResponse

router = APIRouter(prefix="/system", tags=["system"])


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    },
)
async def read_system_status(
    principal: CurrentPrincipal,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> SystemStatusResponse:
    """Expose the final bounded service-status signature."""
    limit = enforce_auth_action_rate_limit(
        redis_client,
        action="ordinary-read",
        identity=str(principal.user_id),
        client_ip="server-principal",
        limit=ORDINARY_READ_LIMIT,
    )
    if not limit.allowed:
        raise_rate_limited(limit)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")
