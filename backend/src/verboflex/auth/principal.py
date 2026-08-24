"""Database-backed authenticated-principal seams."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.api.v1.routes.auth import OptionalBearerToken
from verboflex.auth.access_tokens import (
    InvalidAccessToken,
    PasswordChangeRequired,
    decode_access_token,
)
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.models.auth_session import AuthSession
from verboflex.models.user import User
from verboflex.schemas.users import RoleName


class InvalidPrincipal(PermissionError):
    """Raised when signed claims disagree with current durable authority."""


@dataclass(frozen=True, slots=True)
class Principal:
    """Safe provider-independent authority loaded from durable state."""

    user_id: UUID
    email: str
    display_name: str
    roles: tuple[RoleName, ...]
    must_change_password: bool


def load_principal(
    session: Session,
    access_token: str | None,
    *,
    settings: Settings,
) -> Principal:
    """Resolve verified bearer authority against current PostgreSQL state."""
    if access_token is None:
        raise InvalidPrincipal("missing access token")
    try:
        claims = decode_access_token(access_token, settings=settings)
    except InvalidAccessToken as error:
        raise InvalidPrincipal("invalid access token") from error

    user = session.execute(select(User).where(User.id == claims.user_id)).scalar_one_or_none()
    auth_session = (
        session.get(AuthSession, claims.session_id) if claims.session_id is not None else None
    )
    now = datetime.now(UTC)
    if (
        user is None
        or not user.is_active
        or user.token_version != claims.token_version
        or auth_session is None
        or auth_session.user_id != user.id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
    ):
        raise InvalidPrincipal("invalid access token")
    if user.must_change_password:
        raise PasswordChangeRequired("password change required")

    try:
        roles = tuple(sorted(RoleName(role.name) for role in user.roles))
    except ValueError as error:
        raise InvalidPrincipal("invalid role state") from error
    return Principal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=roles,
        must_change_password=user.must_change_password,
    )


def get_current_principal(
    access_token: OptionalBearerToken,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    """FastAPI dependency for ordinary authenticated resources."""
    try:
        return load_principal(session, access_token, settings=settings)
    except PasswordChangeRequired as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
        ) from error
    except InvalidPrincipal as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_roles(*allowed: RoleName) -> Callable[[Principal], Principal]:
    """Build a reusable dependency accepting any database-loaded allowed role."""
    accepted = frozenset(allowed)
    if not accepted:
        raise ValueError("at least one allowed role is required")

    def dependency(principal: CurrentPrincipal) -> Principal:
        if accepted.isdisjoint(principal.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return principal

    return dependency
