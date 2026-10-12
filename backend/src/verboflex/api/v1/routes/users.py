"""Bounded authenticated user contracts."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal, Principal, require_roles
from verboflex.auth.product_access import operational_roles, visible_product_sql
from verboflex.auth.rate_limits import (
    BoundedLocalRateLimiter,
    enforce_ordinary_read_rate_limit,
    get_local_rate_limiter,
    get_redis_client,
    raise_rate_limited,
)
from verboflex.auth.translation_access import (
    TranslationGroupAccessMode,
    TranslationGroupAccessUnavailable,
    TranslationGroupActionDenied,
    resolve_translation_group_access,
)
from verboflex.core.text import StorableText
from verboflex.db.session import get_db_session
from verboflex.models.product_member import ProductMember
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
    translation_group_id: UUID | None = None,
) -> list[MentionUserResponse]:
    """Return at most eight active internal identities without admin metadata."""
    normalized = q.strip().lower()
    if not normalized:
        return []
    pattern = f"%{_escape_like(normalized)}%"
    product_id = None
    if translation_group_id is not None:
        try:
            product_id = resolve_translation_group_access(
                session,
                principal=_principal,
                translation_group_id=translation_group_id,
                mode=TranslationGroupAccessMode.COMMENT,
            ).product_id
        except TranslationGroupAccessUnavailable, TranslationGroupActionDenied:
            raise HTTPException(404, "Translation unavailable") from None
    users = session.execute(
        text(f"""
        SELECT u.id, u.display_name, u.email FROM users u
        WHERE u.is_active AND (lower(u.display_name) LIKE :pattern ESCAPE '\\'
            OR lower(u.email) LIKE :pattern ESCAPE '\\')
        AND EXISTS (SELECT 1 FROM products product WHERE product.is_active
            AND product.deleted_at IS NULL
            AND (CAST(:product_id AS uuid) IS NULL OR product.id=:product_id)
            AND {visible_product_sql()}
            AND (EXISTS (SELECT 1 FROM product_members pm WHERE pm.user_id=u.id
                     AND pm.product_id=product.id AND pm.active)
                OR EXISTS (SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id
                           WHERE ur.user_id=u.id AND r.name='admin')))
        ORDER BY lower(u.email), u.id LIMIT 8
    """),
        {"pattern": pattern, "principal_id": _principal.user_id, "product_id": product_id},
    ).mappings()
    return [MentionUserResponse.model_validate(dict(user)) for user in users]


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
    session: UserSession,
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
        product_roles={
            member.product_id: list(operational_roles(member.role))
            for member in session.scalars(
                select(ProductMember).where(
                    ProductMember.user_id == principal.user_id, ProductMember.active
                )
            )
        },
        managed_product_ids=list(
            session.scalars(
                select(ProductMember.product_id).where(
                    ProductMember.user_id == principal.user_id,
                    ProductMember.active,
                    ProductMember.role == "product_owner",
                )
            )
        ),
        must_change_password=principal.must_change_password,
    )
