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


def _validated_purpose(payload: dict[str, object], expected: TokenPurpose) -> TokenPurpose:
    raw_purpose = payload["purpose"]
    if raw_purpose not in ("access", "password_change"):
        raise InvalidAccessToken("invalid access token")
    purpose = raw_purpose
    if purpose == expected:
        return purpose
    if purpose == "password_change" and expected == "access":
        raise PasswordChangeRequired("password change required")
    raise InvalidAccessToken("invalid access token")


def _validated_token_version(payload: dict[str, object]) -> int:
    token_version = payload["token_version"]
    if not isinstance(token_version, int) or isinstance(token_version, bool) or token_version < 0:
        raise InvalidAccessToken("invalid access token")
    return token_version


def _validated_session_id(payload: dict[str, object], purpose: TokenPurpose) -> UUID | None:
    session_value = payload.get("sid")
    if purpose == "password_change":
        if session_value is not None:
            raise InvalidAccessToken("invalid access token")
        return None
    if not isinstance(session_value, str):
        raise InvalidAccessToken("invalid access token")
    return UUID(session_value)


def _validated_datetime(payload: dict[str, object], claim: str) -> datetime:
    timestamp = payload[claim]
    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
        raise InvalidAccessToken("invalid access token")
    return datetime.fromtimestamp(timestamp, UTC)


def _claims_from_payload(
    payload: dict[str, object], *, settings: Settings, expected_purpose: TokenPurpose
) -> AccessTokenClaims:
    purpose = _validated_purpose(payload, expected_purpose)
    token_version = _validated_token_version(payload)
    session_id = _validated_session_id(payload, purpose)
    issued_at = _validated_datetime(payload, "iat")
    expires_at = _validated_datetime(payload, "exp")
    lifetime_minutes = (
        settings.access_token_expire_minutes
        if purpose == "access"
        else settings.password_change_token_expire_minutes
    )
    if expires_at - issued_at != timedelta(minutes=lifetime_minutes):
        raise InvalidAccessToken("invalid access token")
    subject = payload["sub"]
    if not isinstance(subject, str):
        raise InvalidAccessToken("invalid access token")
    return AccessTokenClaims(
        user_id=UUID(subject),
        session_id=session_id,
        issued_at=issued_at,
        expires_at=expires_at,
        purpose=purpose,
        token_version=token_version,
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
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": list(COMMON_REQUIRED_CLAIMS)},
            leeway=CLOCK_SKEW_TOLERANCE_SECONDS,
        )
    except jwt.InvalidTokenError as error:
        raise InvalidAccessToken("invalid access token") from error

    try:
        return _claims_from_payload(
            payload,
            settings=settings,
            expected_purpose=expected_purpose,
        )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise InvalidAccessToken("invalid access token") from error
