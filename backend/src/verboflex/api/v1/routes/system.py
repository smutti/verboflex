"""System-status contract stub."""

from fastapi import APIRouter, HTTPException, status

from verboflex.api.v1.routes.auth import OptionalBearerToken
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
async def read_system_status(_access_token: OptionalBearerToken) -> SystemStatusResponse:
    """Expose the final bounded service-status signature."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")
