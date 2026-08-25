"""Hashed opaque refresh-session rotation and revocation."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
INVALID_REFRESH_SESSION_MESSAGE = "invalid refresh session"


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


def _load_predecessor(session: Session, refresh_token: str) -> AuthSession:
    predecessor = session.execute(
        select(AuthSession)
        .where(AuthSession.token_hash == hash_refresh_token(refresh_token))
        .with_for_update()
    ).scalar_one_or_none()
    if predecessor is None:
        raise InvalidRefreshSession(INVALID_REFRESH_SESSION_MESSAGE)
    return predecessor


def _revoke_replayed_family(
    session: Session, predecessor: AuthSession, *, rotated_at: datetime
) -> bool:
    if predecessor.used_at is None:
        return False
    session.execute(
        update(AuthSession)
        .where(AuthSession.family_id == predecessor.family_id)
        .values(revoked_at=rotated_at)
    )
    return True


def _require_refresh_user(
    session: Session, predecessor: AuthSession, *, rotated_at: datetime
) -> User:
    if predecessor.revoked_at is not None or predecessor.expires_at <= rotated_at:
        raise InvalidRefreshSession(INVALID_REFRESH_SESSION_MESSAGE)
    user = session.get(User, predecessor.user_id)
    if user is None or not user.is_active or user.must_change_password:
        raise InvalidRefreshSession(INVALID_REFRESH_SESSION_MESSAGE)
    return user


def _create_successor_authority(
    session: Session,
    predecessor: AuthSession,
    user: User,
    *,
    settings: Settings,
    rotated_at: datetime,
) -> RefreshAuthority:
    successor_token = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
    successor = AuthSession(
        user_id=predecessor.user_id,
        family_id=predecessor.family_id,
        parent_id=predecessor.id,
        token_hash=hash_refresh_token(successor_token),
        expires_at=rotated_at + timedelta(days=settings.refresh_token_expire_days),
    )
    predecessor.used_at = rotated_at
    session.add(successor)
    session.flush()
    return RefreshAuthority(
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


def rotate_refresh_session(
    session: Session,
    refresh_token: str | None,
    *,
    settings: Settings,
    now: datetime | None = None,
) -> RefreshAuthority:
    """Atomically consume one refresh token and create exactly one successor."""
    if not _is_well_formed_refresh_token(refresh_token):
        raise InvalidRefreshSession(INVALID_REFRESH_SESSION_MESSAGE)
    assert refresh_token is not None
    rotated_at = now or datetime.now(UTC)

    with session.begin():
        predecessor = _load_predecessor(session, refresh_token)
        if _revoke_replayed_family(session, predecessor, rotated_at=rotated_at):
            authority = None
        else:
            authority = _create_successor_authority(
                session,
                predecessor,
                _require_refresh_user(session, predecessor, rotated_at=rotated_at),
                settings=settings,
                rotated_at=rotated_at,
            )

    if authority is None:
        raise InvalidRefreshSession(INVALID_REFRESH_SESSION_MESSAGE)
    return authority


def revoke_refresh_session(
    session: Session,
    refresh_token: str | None,
    *,
    now: datetime | None = None,
) -> None:
    """Idempotently revoke the session named by a valid-looking cookie."""
    if not _is_well_formed_refresh_token(refresh_token):
        return
    assert refresh_token is not None
    revoked_at = now or datetime.now(UTC)
    with session.begin():
        auth_session = session.execute(
            select(AuthSession)
            .where(AuthSession.token_hash == hash_refresh_token(refresh_token))
            .with_for_update()
        ).scalar_one_or_none()
        if auth_session is not None and auth_session.revoked_at is None:
            auth_session.revoked_at = revoked_at
