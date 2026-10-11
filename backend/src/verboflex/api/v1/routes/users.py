"""Bounded authenticated user contracts."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from redis import Redis
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal, Principal, require_roles
from verboflex.auth.rate_limits import (
    BoundedLocalRateLimiter,
    enforce_ordinary_read_rate_limit,
    get_local_rate_limiter,
    get_redis_client,
    raise_rate_limited,
)
from verboflex.core.text import StorableText
from verboflex.db.session import get_db_session
from verboflex.models.user import User
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import CurrentUserResponse, MentionUserResponse, RoleName

router = APIRouter(prefix="/users", tags=["users"])
MentionAuthorPrincipal = Annotated[
    Principal,
    Depends(
        require_roles(
            RoleName.ADMIN,
            RoleName.PRODUCT_MANAGER_REVIEWER,
            RoleName.TRANSLATOR,
        )
    ),
]
UserSession = Annotated[Session, Depends(get_db_session, use_cache=False)]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get(
    "/mentions",
    operation_id="searchMentionUsers",
    response_model=list[MentionUserResponse],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def search_mention_users(
    _principal: MentionAuthorPrincipal,
    session: UserSession,
    q: Annotated[StorableText, Query(min_length=1, max_length=200)],
) -> list[MentionUserResponse]:
    """Return at most eight active internal identities without admin metadata."""
    normalized = q.strip().lower()
    if not normalized:
        return []
    pattern = f"%{_escape_like(normalized)}%"
    users = tuple(
        session.scalars(
            select(User)
            .where(
                User.is_active.is_(True),
                or_(
                    func.lower(User.display_name).like(pattern, escape="\\"),
                    func.lower(User.email).like(pattern, escape="\\"),
                ),
            )
            .order_by(func.lower(User.email), User.id)
            .limit(8)
        )
    )
    return [
        MentionUserResponse(id=user.id, display_name=user.display_name, email=user.email)
        for user in users
    ]


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
