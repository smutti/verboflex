"""Public liveness route."""

from fastapi import APIRouter, HTTPException, status

from verboflex.schemas.system import ErrorResponse, HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse}},
)
async def read_health() -> HealthResponse:
    """Return the callable pre-implementation health seam."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")
