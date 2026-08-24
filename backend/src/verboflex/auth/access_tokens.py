"""Signed short-lived access authority seams."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import jwt

from verboflex.core.config import Settings

TokenPurpose = Literal["access", "password_change"]


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Validated provider-independent authority carried by a bearer token."""

    user_id: UUID
    session_id: UUID | None
    issued_at: datetime
    expires_at: datetime
    purpose: TokenPurpose
    token_version: int


def issue_access_token(
    *,
    user_id: UUID,
    token_version: int,
    purpose: TokenPurpose,
    settings: Settings,
    session_id: UUID | None = None,
    now: datetime | None = None,
) -> str:
    """Issue signed authority with the approved purpose-specific lifetime."""
    if purpose != "access":
        raise NotImplementedError
    if session_id is None:
        raise ValueError("ordinary access tokens require a session id")
    if settings.jwt_secret_key is None:
        raise RuntimeError("JWT signing secret is not configured")

    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, str | int] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "purpose": purpose,
        "token_version": token_version,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(
    token: str,
    *,
    settings: Settings,
    expected_purpose: TokenPurpose = "access",
) -> AccessTokenClaims:
    """Verify and decode one bearer token for the expected authority purpose."""
    raise NotImplementedError
