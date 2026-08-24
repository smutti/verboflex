"""Atomic current-user password replacement and authority revocation."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from verboflex.auth.access_tokens import (
    AccessTokenClaims,
    InvalidAccessToken,
    PasswordChangeRequired,
    decode_access_token,
)
from verboflex.auth.passwords import (
    PasswordPolicyError,
    hash_password,
    validate_password_for_user,
    verify_password,
)
from verboflex.core.config import Settings
from verboflex.models.auth_session import AuthSession
from verboflex.models.user import User


class InvalidPasswordChangePrincipal(PermissionError):
    """Raised when bearer claims lack current durable password-change authority."""


class IncorrectCurrentPassword(ValueError):
    """Raised through the exact current-credential error surface."""


class PasswordChangePolicyError(ValueError):
    """Expose one approved stable password-policy detail."""


@dataclass(frozen=True, slots=True)
class PasswordChangeCandidate:
    """Cryptographically verified candidate used for pre-database limiting."""

    claims: AccessTokenClaims

    @property
    def rate_limit_identity(self) -> str:
        return str(self.claims.user_id)


def decode_password_change_candidate(
    access_token: str | None,
    *,
    settings: Settings,
) -> PasswordChangeCandidate:
    """Accept ordinary or restricted bearer purpose only at this endpoint."""
    if access_token is None:
        raise InvalidPasswordChangePrincipal("invalid access token")
    try:
        try:
            claims = decode_access_token(access_token, settings=settings)
        except PasswordChangeRequired:
            claims = decode_access_token(
                access_token,
                settings=settings,
                expected_purpose="password_change",
            )
    except (InvalidAccessToken, PasswordChangeRequired) as error:
        raise InvalidPasswordChangePrincipal("invalid access token") from error
    return PasswordChangeCandidate(claims=claims)


def replace_current_password(
    session: Session,
    candidate: PasswordChangeCandidate,
    *,
    current_password: str,
    new_password: str,
    now: datetime | None = None,
) -> None:
    """Replace one current credential and revoke all old authority atomically."""
    changed_at = now or datetime.now(UTC)
    claims = candidate.claims
    with session.begin():
        user = session.execute(
            select(User).where(User.id == claims.user_id).with_for_update()
        ).scalar_one_or_none()
        if (
            user is None
            or not user.is_active
            or user.token_version != claims.token_version
            or (claims.purpose == "password_change" and not user.must_change_password)
        ):
            raise InvalidPasswordChangePrincipal("invalid access token")

        if claims.purpose == "access":
            auth_session = (
                session.execute(
                    select(AuthSession).where(AuthSession.id == claims.session_id).with_for_update()
                ).scalar_one_or_none()
                if claims.session_id is not None
                else None
            )
            if (
                auth_session is None
                or auth_session.user_id != user.id
                or auth_session.revoked_at is not None
                or auth_session.expires_at <= changed_at
            ):
                raise InvalidPasswordChangePrincipal("invalid access token")

        if not verify_password(current_password, user.hashed_password):
            raise IncorrectCurrentPassword("current password is incorrect")
        try:
            validate_password_for_user(
                new_password,
                normalized_email=user.email,
                current_password_hash=user.hashed_password,
            )
        except PasswordPolicyError as error:
            details = {
                "password must contain 12 to 128 characters": (
                    "Password must contain 12 to 128 characters"
                ),
                "password must not equal login email": "Password must not equal login email",
                "password must differ from current password": (
                    "New password must differ from current password"
                ),
            }
            raise PasswordChangePolicyError(details[str(error)]) from error

        user.hashed_password = hash_password(new_password)
        user.must_change_password = False
        user.token_version += 1
        session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=changed_at)
        )
