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
INVALID_ACCESS_TOKEN_MESSAGE = "invalid access token"
PASSWORD_CHANGE_REQUIRED_MESSAGE = "password change required"
JWT_SECRET_MISSING_MESSAGE = "JWT signing secret is not configured"
ORDINARY_SESSION_REQUIRED_MESSAGE = "ordinary access tokens require a session id"
PASSWORD_CHANGE_SESSION_FORBIDDEN_MESSAGE = "password change tokens must not carry a session id"


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
        raise ValueError(ORDINARY_SESSION_REQUIRED_MESSAGE)
    if purpose == "password_change" and session_id is not None:
        raise ValueError(PASSWORD_CHANGE_SESSION_FORBIDDEN_MESSAGE)
    if settings.jwt_secret_key is None:
        raise RuntimeError(JWT_SECRET_MISSING_MESSAGE)

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
        raise InvalidAccessToken(INVALID_ACCESS_TOKEN_MESSAGE)
    purpose = raw_purpose
    if purpose == expected:
        return purpose
    if purpose == "password_change" and expected == "access":
        raise PasswordChangeRequired(PASSWORD_CHANGE_REQUIRED_MESSAGE)
    raise InvalidAccessToken(INVALID_ACCESS_TOKEN_MESSAGE)


def _validated_token_version(payload: dict[str, object]) -> int:
    token_version = payload["token_version"]
    if not isinstance(token_version, int) or isinstance(token_version, bool) or token_version < 0:
        raise InvalidAccessToken(INVALID_ACCESS_TOKEN_MESSAGE)
    return token_version


def _validated_session_id(payload: dict[str, object], purpose: TokenPurpose) -> UUID | None:
    session_value = payload.get("sid")
    if purpose == "password_change":
        if session_value is not None:
            raise InvalidAccessToken(INVALID_ACCESS_TOKEN_MESSAGE)
        return None
    if not isinstance(session_value, str):
        raise InvalidAccessToken(INVALID_ACCESS_TOKEN_MESSAGE)
    return UUID(session_value)


def _validated_datetime(payload: dict[str, object], claim: str) -> datetime:
    timestamp = payload[claim]
    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
        raise InvalidAccessToken(INVALID_ACCESS_TOKEN_MESSAGE)
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
        raise InvalidAccessToken(INVALID_ACCESS_TOKEN_MESSAGE)
    subject = payload["sub"]
    if not isinstance(subject, str):
        raise InvalidAccessToken(INVALID_ACCESS_TOKEN_MESSAGE)
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
        raise RuntimeError(JWT_SECRET_MISSING_MESSAGE)
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": list(COMMON_REQUIRED_CLAIMS)},
            leeway=CLOCK_SKEW_TOLERANCE_SECONDS,
        )
    except jwt.InvalidTokenError as error:
        raise InvalidAccessToken(INVALID_ACCESS_TOKEN_MESSAGE) from error

    try:
        return _claims_from_payload(
            payload,
            settings=settings,
            expected_purpose=expected_purpose,
        )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise InvalidAccessToken(INVALID_ACCESS_TOKEN_MESSAGE) from error
