"""Privileged non-secret administrative command seams."""

import argparse
from datetime import UTC, datetime
from typing import Protocol, Sequence

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from verboflex.auth.identity import ASCII_WHITESPACE, normalize_email
from verboflex.auth.passwords import hash_password, validate_password_for_user
from verboflex.models.auth_session import AuthSession
from verboflex.models.role import Role
from verboflex.models.user import User

FIRST_ADMIN_LOCK_KEY = 0x564552424F464C58


class SessionProvider(Protocol):
    """Callable that returns an independent SQLAlchemy session."""

    def __call__(self) -> Session: ...


class PasswordReader(Protocol):
    """Callable secret-input boundary used by the CLI and its tests."""

    def __call__(self, prompt: str) -> str: ...


class BootstrapAdminError(RuntimeError):
    """Raised when the database is not eligible for first-admin bootstrap."""


class ResetPasswordError(RuntimeError):
    """Raised when an administrative reset cannot identify its account."""


def bootstrap_first_admin(
    session: Session,
    *,
    email: str,
    display_name: str,
    password: str,
) -> User:
    """Create the only eligible first admin under a PostgreSQL transaction lock."""
    normalized_email = normalize_email(email)
    normalized_display_name = display_name.strip(ASCII_WHITESPACE)
    if not normalized_display_name:
        raise BootstrapAdminError("display name is required")
    password_hash = hash_password(password)

    with session.begin():
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": FIRST_ADMIN_LOCK_KEY},
        )
        if session.scalar(select(func.count()).select_from(User)) != 0:
            raise BootstrapAdminError("bootstrap refused: users already exist")
        admin_role = session.execute(select(Role).where(Role.name == "admin")).scalar_one_or_none()
        if admin_role is None:
            raise BootstrapAdminError("bootstrap refused: admin role is unavailable")

        user = User(
            email=normalized_email,
            display_name=normalized_display_name,
            hashed_password=password_hash,
            is_active=True,
            must_change_password=True,
            token_version=0,
            roles=[admin_role],
        )
        session.add(user)
        session.flush()
        return user


def reset_user_password(
    session: Session,
    *,
    email: str,
    password: str,
) -> None:
    """Replace one user's credential and revoke all authority atomically."""
    normalized_email = normalize_email(email)
    with session.begin():
        user = session.execute(
            select(User).where(User.email == normalized_email).with_for_update()
        ).scalar_one_or_none()
        if user is None:
            raise ResetPasswordError("reset refused: account unavailable")

        validate_password_for_user(
            password,
            normalized_email=normalized_email,
            current_password_hash=user.hashed_password,
        )
        user.hashed_password = hash_password(password)
        user.must_change_password = True
        user.token_version += 1
        session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        session.flush()


def build_parser() -> argparse.ArgumentParser:
    """Callable RED seam for the non-secret command-line contract."""
    parser = argparse.ArgumentParser(prog="verboflex")
    parser.add_subparsers(dest="command")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    password_reader: PasswordReader | None = None,
    session_provider: SessionProvider | None = None,
) -> int:
    """Callable RED seam for the administrative command dispatcher."""
    return 0
