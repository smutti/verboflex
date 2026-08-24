"""Property and boundary contracts for identity and password primitives."""

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from verboflex.auth.identity import normalize_email
from verboflex.auth.passwords import (
    PasswordPolicyError,
    hash_password,
    validate_password,
    verify_password,
)

ASCII_WHITESPACE = " \t\n\r\f\v"


@given(
    local=st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=24),
    domain=st.text(alphabet=string.ascii_letters, min_size=1, max_size=16),
    leading=st.text(alphabet=ASCII_WHITESPACE, max_size=4),
    trailing=st.text(alphabet=ASCII_WHITESPACE, max_size=4),
)
def test_corporate_email_normalization_is_idempotent(
    local: str,
    domain: str,
    leading: str,
    trailing: str,
) -> None:
    """Trim surrounding ASCII whitespace, lowercase, and remain stable."""
    supplied = f"{leading}{local}@{domain}.example{trailing}"

    normalized = normalize_email(supplied)

    assert normalized == f"{local}@{domain}.example".lower()
    assert normalize_email(normalized) == normalized


def test_corporate_email_normalization_handles_the_approved_example() -> None:
    """Mixed-case padded login identifiers resolve to one canonical value."""
    assert normalize_email(" \tPERSON@EXAMPLE.COM\r\n") == "person@example.com"


def test_unicode_and_space_password_is_stored_only_as_argon2() -> None:
    """Approved Unicode and space-containing passwords survive secure hashing."""
    password = "  密碼 phrase 2026!  "

    validate_password(password)
    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2")
    assert verify_password(password, password_hash) is True
    assert verify_password(password + "wrong", password_hash) is False


@pytest.mark.parametrize("invalid_password", ["x" * 11, "x" * 129])
def test_password_character_boundaries_are_12_through_128(
    invalid_password: str,
) -> None:
    """Character counts outside the inclusive approved interval fail closed."""
    with pytest.raises(PasswordPolicyError, match="12 to 128 characters"):
        validate_password(invalid_password)


@given(
    st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)),
        min_size=12,
        max_size=128,
    )
)
def test_every_generated_approved_unicode_length_passes(password: str) -> None:
    """The policy uses Unicode character count and invents no composition rule."""
    validate_password(password)
