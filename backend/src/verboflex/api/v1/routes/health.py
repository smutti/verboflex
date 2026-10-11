"""Public bounded liveness route."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from verboflex.auth.rate_limits import enforce_health_rate_limit
from verboflex.schemas.system import ErrorResponse, HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    operation_id="read_health",
    response_model=HealthResponse,
    responses={status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse}},
)
async def read_health(
    _rate_limit: Annotated[None, Depends(enforce_health_rate_limit)],
) -> HealthResponse:
    """Return the constant public liveness payload."""
    return HealthResponse(status="ok")
