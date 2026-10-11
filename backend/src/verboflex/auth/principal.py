"""Database-backed authenticated-principal seams."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
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

INVALID_PRINCIPAL_MESSAGE = "invalid access token"
MISSING_ACCESS_TOKEN_MESSAGE = "missing access token"
INVALID_ROLE_STATE_MESSAGE = "invalid role state"
PASSWORD_CHANGE_REQUIRED_MESSAGE = "password change required"
PASSWORD_CHANGE_REQUIRED_DETAIL = "Password change required"
INVALID_ACCESS_TOKEN_DETAIL = "Invalid access token"
BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


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
    session_id: UUID | None = None


def _require_current_user(user: User | None, *, token_version: int) -> User:
    if user is None or not user.is_active or user.token_version != token_version:
        raise InvalidPrincipal(INVALID_PRINCIPAL_MESSAGE)
    return user


def _require_current_session(
    auth_session: AuthSession | None, *, user_id: UUID, now: datetime
) -> None:
    if auth_session is None:
        raise InvalidPrincipal(INVALID_PRINCIPAL_MESSAGE)
    if auth_session.user_id != user_id:
        raise InvalidPrincipal(INVALID_PRINCIPAL_MESSAGE)
    if auth_session.revoked_at is not None or auth_session.expires_at <= now:
        raise InvalidPrincipal(INVALID_PRINCIPAL_MESSAGE)


def load_principal(
    session: Session,
    access_token: str | None,
    *,
    settings: Settings,
) -> Principal:
    """Resolve verified bearer authority against current PostgreSQL state."""
    if access_token is None:
        raise InvalidPrincipal(MISSING_ACCESS_TOKEN_MESSAGE)
    try:
        claims = decode_access_token(access_token, settings=settings)
    except InvalidAccessToken as error:
        raise InvalidPrincipal(INVALID_PRINCIPAL_MESSAGE) from error

    user = _require_current_user(
        session.execute(select(User).where(User.id == claims.user_id)).scalar_one_or_none(),
        token_version=claims.token_version,
    )
    auth_session = (
        session.get(AuthSession, claims.session_id) if claims.session_id is not None else None
    )
    _require_current_session(auth_session, user_id=user.id, now=datetime.now(UTC))
    if user.must_change_password:
        raise PasswordChangeRequired(PASSWORD_CHANGE_REQUIRED_MESSAGE)

    try:
        roles = tuple(sorted(RoleName(role.name) for role in user.roles))
    except ValueError as error:
        raise InvalidPrincipal(INVALID_ROLE_STATE_MESSAGE) from error
    return Principal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=roles,
        must_change_password=user.must_change_password,
        session_id=claims.session_id,
    )


def get_current_principal(
    request: Request,
    access_token: OptionalBearerToken,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    """FastAPI dependency for ordinary authenticated resources."""
    internal_principal = request.scope.get("verboflex.mcp_principal")
    if isinstance(internal_principal, Principal):
        return internal_principal
    try:
        return load_principal(session, access_token, settings=settings)
    except PasswordChangeRequired as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PASSWORD_CHANGE_REQUIRED_DETAIL,
        ) from error
    except InvalidPrincipal as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_ACCESS_TOKEN_DETAIL,
            headers=BEARER_CHALLENGE,
        ) from error
    finally:
        # Principal is an immutable value, with roles already materialized.
        # Release this read-only lease before a route opens its own transaction;
        # otherwise concurrent requests can each hold one connection while all
        # wait for a second connection from the same finite pool.
        session.rollback()


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
