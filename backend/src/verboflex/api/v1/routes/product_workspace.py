"""Ordinary authenticated product discovery and repository coverage."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
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
from verboflex.db.session import get_db_session
from verboflex.schemas.product_workspace import ProductWorkspacePage, ProductWorkspaceQuery
from verboflex.schemas.system import ErrorResponse
from verboflex.services.product_workspace import list_product_workspaces

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "/workspace",
    operation_id="listProductWorkspaces",
    response_model=ProductWorkspacePage,
    responses={code: {"model": ErrorResponse} for code in (401, 403, 429, 503)},
)
def read_product_workspaces(
    principal: CurrentPrincipal,
    session: Annotated[Session, Depends(get_db_session, use_cache=False)],
    response: Response,
    query: Annotated[ProductWorkspaceQuery, Query()],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    local_limiter: Annotated[BoundedLocalRateLimiter, Depends(get_local_rate_limiter)],
) -> ProductWorkspacePage:
    limit = enforce_ordinary_read_rate_limit(
        redis_client, local_limiter, user_id=str(principal.user_id)
    )
    if not limit.allowed:
        raise_rate_limited(limit)
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return list_product_workspaces(session, query=query)
    except Exception as error:
        logger.exception("product workspace read failed", exc_info=error)
        raise HTTPException(status_code=503, detail="Products unavailable") from error
