"""Signed short-lived access authority seams."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import jwt

from verboflex.core.config import Settings

TokenPurpose = Literal["access", "password_change"]
CLOCK_SKEW_TOLERANCE_SECONDS = 5
COMMON_REQUIRED_CLAIMS = ("sub", "iat", "exp", "purpose", "token_version")


class InvalidAccessToken(ValueError):
    """Raised when bearer authority is malformed, untrusted, or expired."""


class PasswordChangeRequired(PermissionError):
    """Raised when restricted authority reaches an ordinary resource."""


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
    if purpose == "access" and session_id is None:
        raise ValueError("ordinary access tokens require a session id")
    if purpose == "password_change" and session_id is not None:
        raise ValueError("password change tokens must not carry a session id")
    if settings.jwt_secret_key is None:
        raise RuntimeError("JWT signing secret is not configured")

    issued_at = now or datetime.now(UTC)
    lifetime_minutes = (
        settings.access_token_expire_minutes
        if purpose == "access"
        else settings.password_change_token_expire_minutes
    )
    expires_at = issued_at + timedelta(minutes=lifetime_minutes)
    payload: dict[str, str | int] = {
        "sub": str(user_id),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "purpose": purpose,
        "token_version": token_version,
    }
    if session_id is not None:
        payload["sid"] = str(session_id)
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
    if settings.jwt_secret_key is None:
        raise RuntimeError("JWT signing secret is not configured")
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        options={"require": list(COMMON_REQUIRED_CLAIMS)},
        leeway=CLOCK_SKEW_TOLERANCE_SECONDS,
    )
    purpose = payload["purpose"]
    if purpose != expected_purpose:
        raise ValueError("token purpose is not valid for this resource")
    if not isinstance(payload["token_version"], int) or isinstance(
        payload["token_version"], bool
    ):
        raise ValueError("token version must be an integer")

    session_value = payload.get("sid")
    if purpose == "access" and session_value is None:
        raise ValueError("ordinary access token is missing its session id")
    if purpose == "password_change" and session_value is not None:
        raise ValueError("password change token must not carry a session id")

    issued_at = datetime.fromtimestamp(payload["iat"], UTC)
    expires_at = datetime.fromtimestamp(payload["exp"], UTC)
    return AccessTokenClaims(
        user_id=UUID(payload["sub"]),
        session_id=UUID(session_value) if session_value is not None else None,
        issued_at=issued_at,
        expires_at=expires_at,
        purpose=purpose,
        token_version=payload["token_version"],
    )
