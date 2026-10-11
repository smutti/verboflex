"""System-status contract stub."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.auth.rate_limits import (
    BoundedLocalRateLimiter,
    enforce_ordinary_read_rate_limit,
    get_local_rate_limiter,
    get_redis_client,
    raise_rate_limited,
)
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.schemas.system import ErrorResponse, ServiceState, SystemStatusResponse
from verboflex.services.system_status import SystemStatusService, probe_default_worker

router = APIRouter(prefix="/system", tags=["system"])


def get_system_status_service(
    session: Annotated[Session, Depends(get_db_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SystemStatusService:
    """Build real timeout-bounded database, Redis, and worker probes."""

    def database_probe() -> ServiceState:
        session.execute(text("SELECT 1")).scalar_one()
        return "online"

    def redis_probe() -> ServiceState:
        return "online" if redis_client.ping() else "unavailable"

    return SystemStatusService(
        database_probe=database_probe,
        redis_probe=redis_probe,
        worker_probe=lambda: probe_default_worker(
            # Celery's inspect timeout is followed by a small protocol cleanup
            # cost. Keep it comfortably inside the public bounded probe so a
            # healthy worker is not projected as unavailable at the deadline.
            timeout_seconds=settings.service_probe_timeout_seconds / 2,
        ),
        timeout_seconds=settings.service_probe_timeout_seconds,
    )


@router.get(
    "/status",
    operation_id="read_system_status",
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
    local_limiter: Annotated[BoundedLocalRateLimiter, Depends(get_local_rate_limiter)],
    service: Annotated[SystemStatusService, Depends(get_system_status_service)],
) -> SystemStatusResponse:
    """Expose the final bounded service-status signature."""
    limit = enforce_ordinary_read_rate_limit(
        redis_client,
        local_limiter,
        user_id=str(principal.user_id),
    )
    if not limit.allowed:
        raise_rate_limited(limit)
    snapshot = await service.collect()
    return SystemStatusResponse(
        api="online",
        database=snapshot.database,
        redis=snapshot.redis,
        worker=snapshot.worker,
        checked_at=snapshot.checked_at,
    )
