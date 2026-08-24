"""Privileged non-secret administrative command seams."""

from sqlalchemy.orm import Session

from verboflex.models.user import User


class BootstrapAdminError(RuntimeError):
    """Raised when the database is not eligible for first-admin bootstrap."""


def bootstrap_first_admin(
    session: Session,
    *,
    email: str,
    display_name: str,
    password: str,
) -> User | None:
    """Callable RED seam for atomic first-admin bootstrap."""
    return None
