"""Privileged non-secret administrative command seams."""

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from verboflex.auth.identity import ASCII_WHITESPACE, normalize_email
from verboflex.auth.passwords import hash_password
from verboflex.models.role import Role
from verboflex.models.user import User

FIRST_ADMIN_LOCK_KEY = 0x564552424F464C58


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
) -> int:
    """Callable RED seam for atomic credential reset and revocation."""
    return 0
