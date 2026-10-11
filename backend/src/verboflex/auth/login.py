"""Internal credential-exchange seams."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.identity import ASCII_WHITESPACE, normalize_email
from verboflex.auth.passwords import hash_password, verify_password
from verboflex.auth.rate_limits import RedisRateLimitClient, enforce_login_rate_limit
from verboflex.core.config import Settings
from verboflex.models.auth_session import AuthSession
from verboflex.models.user import User

LOGIN_RATE_LIMITED_MESSAGE = "login rate limit exceeded"
INVALID_CREDENTIALS_MESSAGE = "invalid credentials"


class InvalidCredentials(PermissionError):
    """Raised for every invalid, unknown, or inactive credential combination."""


class LoginRateLimited(RuntimeError):
    """Raised before password verification after the fixed-window limit."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(LOGIN_RATE_LIMITED_MESSAGE)
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class LoginAuthority:
    """Authority and optional refresh material returned by a valid login."""

    access_token: str
    expires_in: int
    must_change_password: bool
    refresh_token: str | None


def authenticate_login(
    session: Session,
    redis_client: RedisRateLimitClient,
    *,
    email: str,
    password: str,
    client_ip: str,
    settings: Settings,
) -> LoginAuthority:
    """Authenticate one internal account after enforcing its Redis limit."""
    try:
        normalized_email = normalize_email(email)
    except ValueError:
        normalized_email = email.strip(ASCII_WHITESPACE).lower()
        user_query = None
    else:
        user_query = select(User).where(User.email == normalized_email)

    limit = enforce_login_rate_limit(
        redis_client,
        normalized_email=normalized_email,
        client_ip=client_ip,
    )
    if not limit.allowed:
        raise LoginRateLimited(limit.retry_after)

    user = session.execute(user_query).scalar_one_or_none() if user_query is not None else None
    password_hash = user.hashed_password if user is not None else _dummy_password_hash()
    password_matches = verify_password(password, password_hash)
    if user is None or not password_matches or not user.is_active:
        raise InvalidCredentials(INVALID_CREDENTIALS_MESSAGE)
    if user.must_change_password:
        access_token = issue_access_token(
            user_id=user.id,
            token_version=user.token_version,
            purpose="password_change",
            settings=settings,
        )
        return LoginAuthority(
            access_token=access_token,
            expires_in=settings.password_change_token_expire_minutes * 60,
            must_change_password=True,
            refresh_token=None,
        )

    now = datetime.now(UTC)
    refresh_token = secrets.token_urlsafe(32)
    auth_session = AuthSession(
        id=uuid4(),
        user_id=user.id,
        family_id=uuid4(),
        token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
    )
    access_token = issue_access_token(
        user_id=user.id,
        session_id=auth_session.id,
        token_version=user.token_version,
        purpose="access",
        settings=settings,
        now=now,
    )
    session.add(auth_session)
    session.commit()
    return LoginAuthority(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
        must_change_password=False,
        refresh_token=refresh_token,
    )


@lru_cache
def _dummy_password_hash() -> str:
    """Return one process-local Argon2 target for unknown-identity verification."""
    return hash_password("non-credential dummy verification phrase")
