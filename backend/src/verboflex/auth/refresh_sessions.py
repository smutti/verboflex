"""Hashed opaque refresh-session rotation and revocation."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from verboflex.auth.access_tokens import issue_access_token
from verboflex.core.config import Settings
from verboflex.models.auth_session import AuthSession
from verboflex.models.user import User

REFRESH_TOKEN_BYTES = 32
REFRESH_TOKEN_LENGTH = 43
REFRESH_TOKEN_ALPHABET = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)


class InvalidRefreshSession(PermissionError):
    """Raised through the stable refresh-denial surface."""


@dataclass(frozen=True, slots=True)
class RefreshAuthority:
    """New access and refresh authority returned after one rotation."""

    access_token: str
    refresh_token: str
    expires_in: int


def hash_refresh_token(token: str) -> str:
    """Return the only durable representation of an opaque refresh token."""
    return hashlib.sha256(token.encode()).hexdigest()


def _is_well_formed_refresh_token(token: str | None) -> bool:
    return (
        token is not None
        and len(token) == REFRESH_TOKEN_LENGTH
        and all(character in REFRESH_TOKEN_ALPHABET for character in token)
    )


def rotate_refresh_session(
    session: Session,
    refresh_token: str | None,
    *,
    settings: Settings,
    now: datetime | None = None,
) -> RefreshAuthority:
    """Atomically consume one refresh token and create exactly one successor."""
    if not _is_well_formed_refresh_token(refresh_token):
        raise InvalidRefreshSession("invalid refresh session")
    assert refresh_token is not None
    rotated_at = now or datetime.now(UTC)
    replay_detected = False
    authority: RefreshAuthority | None = None

    with session.begin():
        predecessor = session.execute(
            select(AuthSession)
            .where(AuthSession.token_hash == hash_refresh_token(refresh_token))
            .with_for_update()
        ).scalar_one_or_none()
        if predecessor is None:
            raise InvalidRefreshSession("invalid refresh session")

        if predecessor.used_at is not None:
            session.execute(
                update(AuthSession)
                .where(AuthSession.family_id == predecessor.family_id)
                .values(revoked_at=rotated_at)
            )
            replay_detected = True
        elif predecessor.revoked_at is not None or predecessor.expires_at <= rotated_at:
            raise InvalidRefreshSession("invalid refresh session")
        else:
            user = session.get(User, predecessor.user_id)
            if user is None or not user.is_active or user.must_change_password:
                raise InvalidRefreshSession("invalid refresh session")
            successor_token = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
            successor = AuthSession(
                id=uuid4(),
                user_id=predecessor.user_id,
                family_id=predecessor.family_id,
                parent_id=predecessor.id,
                token_hash=hash_refresh_token(successor_token),
                expires_at=rotated_at + timedelta(days=settings.refresh_token_expire_days),
            )
            predecessor.used_at = rotated_at
            session.add(successor)
            session.flush()
            authority = RefreshAuthority(
                access_token=issue_access_token(
                    user_id=user.id,
                    session_id=successor.id,
                    token_version=user.token_version,
                    purpose="access",
                    settings=settings,
                    now=rotated_at,
                ),
                refresh_token=successor_token,
                expires_in=settings.access_token_expire_minutes * 60,
            )

    if replay_detected or authority is None:
        raise InvalidRefreshSession("invalid refresh session")
    return authority
