"""Authenticated personal dashboard, with normal bounded read limiting."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from redis import Redis
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
from verboflex.schemas.dashboard import DashboardResponse, ProjectUpdatesPage
from verboflex.schemas.system import ErrorResponse
from verboflex.services.dashboard import get_personal_dashboard, get_project_updates
from verboflex.services.signed_cursor import InvalidSignedCursor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])
DashboardSession = Annotated[Session, Depends(get_db_session, use_cache=False)]


class DashboardQuery(BaseModel):
    """No caller-controlled identity, product filters, or unbounded page sizes."""

    model_config = ConfigDict(extra="forbid")


@router.get(
    "",
    operation_id="getPersonalDashboard",
    response_model=DashboardResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {
            "description": "Validation Error",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}
            },
        },
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def read_personal_dashboard(
    principal: CurrentPrincipal,
    session: DashboardSession,
    response: Response,
    query: Annotated[DashboardQuery, Query()],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    local_limiter: Annotated[BoundedLocalRateLimiter, Depends(get_local_rate_limiter)],
) -> DashboardResponse:
    limit = enforce_ordinary_read_rate_limit(
        redis_client, local_limiter, user_id=str(principal.user_id)
    )
    if not limit.allowed:
        raise_rate_limited(limit)
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return get_personal_dashboard(session, principal=principal)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail="Insufficient permissions") from error
    except Exception as error:
        logger.exception("dashboard read failed", exc_info=error)
        raise HTTPException(status_code=503, detail="Dashboard unavailable") from error


class ProjectUpdatesQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)


@router.get(
    "/project-updates",
    operation_id="listProjectUpdates",
    response_model=ProjectUpdatesPage,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {
            "description": "Invalid cursor or query",
            "content": {
                "application/json": {
                    "schema": {
                        "anyOf": [
                            {"$ref": "#/components/schemas/ErrorResponse"},
                            {"$ref": "#/components/schemas/HTTPValidationError"},
                        ]
                    }
                }
            },
        },
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def read_project_updates(
    principal: CurrentPrincipal,
    session: DashboardSession,
    response: Response,
    query: Annotated[ProjectUpdatesQuery, Query()],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    local_limiter: Annotated[BoundedLocalRateLimiter, Depends(get_local_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProjectUpdatesPage:
    limit = enforce_ordinary_read_rate_limit(
        redis_client, local_limiter, user_id=str(principal.user_id)
    )
    if not limit.allowed:
        raise_rate_limited(limit)
    response.headers["Cache-Control"] = "private, no-store"
    try:
        if settings.jwt_secret_key is None:
            raise RuntimeError("signing unavailable")
        return get_project_updates(
            session,
            principal=principal,
            cursor=query.cursor,
            secret=settings.jwt_secret_key.get_secret_value(),
        )
    except InvalidSignedCursor as error:
        raise HTTPException(422, "Invalid cursor") from error
    except PermissionError as error:
        raise HTTPException(403, "Insufficient permissions") from error
    except Exception as error:
        logger.exception("project updates read failed", exc_info=error)
        raise HTTPException(503, "Project updates unavailable") from error


@router.get(
    "/my-activity",
    operation_id="listMyActivity",
    response_model=ProjectUpdatesPage,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {
            "description": "Invalid cursor or query",
            "content": {
                "application/json": {
                    "schema": {
                        "anyOf": [
                            {"$ref": "#/components/schemas/ErrorResponse"},
                            {"$ref": "#/components/schemas/HTTPValidationError"},
                        ]
                    }
                }
            },
        },
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def read_my_activity(
    principal: CurrentPrincipal,
    session: DashboardSession,
    response: Response,
    query: Annotated[ProjectUpdatesQuery, Query()],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    local_limiter: Annotated[BoundedLocalRateLimiter, Depends(get_local_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProjectUpdatesPage:
    limit = enforce_ordinary_read_rate_limit(
        redis_client, local_limiter, user_id=str(principal.user_id)
    )
    if not limit.allowed:
        raise_rate_limited(limit)
    response.headers["Cache-Control"] = "private, no-store"
    try:
        if settings.jwt_secret_key is None:
            raise RuntimeError("signing unavailable")
        return get_project_updates(
            session,
            principal=principal,
            cursor=query.cursor,
            secret=settings.jwt_secret_key.get_secret_value(),
            personal=True,
        )
    except InvalidSignedCursor as error:
        raise HTTPException(422, "Invalid cursor") from error
    except PermissionError as error:
        raise HTTPException(403, "Insufficient permissions") from error
    except Exception as error:
        logger.exception("personal activity read failed", exc_info=error)
        raise HTTPException(503, "Personal activity unavailable") from error
