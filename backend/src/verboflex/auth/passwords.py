"""Password policy and Argon2 hashing seams."""

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

MIN_PASSWORD_CHARACTERS = 12
MAX_PASSWORD_CHARACTERS = 128
PASSWORD_HASHER = PasswordHash.recommended()


class PasswordPolicyError(ValueError):
    """Raised when a password violates the approved Phase 1 policy."""


def validate_password(password: str) -> None:
    """Enforce only the approved inclusive Unicode character-count boundary."""
    if not MIN_PASSWORD_CHARACTERS <= len(password) <= MAX_PASSWORD_CHARACTERS:
        raise PasswordPolicyError("password must contain 12 to 128 characters")


def hash_password(password: str) -> str:
    """Validate and hash a password with the recommended Argon2 hasher."""
    validate_password(password)
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a supplied password while rejecting unknown hash formats safely."""
    try:
        return PASSWORD_HASHER.verify(password, password_hash)
    except UnknownHashError:
        return False


def validate_password_for_user(
    password: str,
    *,
    normalized_email: str,
    current_password_hash: str | None = None,
) -> None:
    """Reject identity-derived or unchanged credentials before persistence."""
    validate_password(password)
    if password.casefold() == normalized_email.casefold():
        raise PasswordPolicyError("password must not equal login email")
    if current_password_hash is not None and verify_password(password, current_password_hash):
        raise PasswordPolicyError("password must differ from current password")
