"""Password policy and Argon2 hashing seams."""


class PasswordPolicyError(ValueError):
    """Raised when a password violates the approved Phase 1 policy."""


def validate_password(password: str) -> None:
    """Callable RED seam for Unicode character-count boundaries."""


def hash_password(password: str) -> str:
    """Callable RED seam for Argon2 hashing."""
    return password


def verify_password(password: str, password_hash: str) -> bool:
    """Callable RED seam for password verification."""
    return False
