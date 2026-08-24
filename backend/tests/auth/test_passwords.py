"""Property and boundary contracts for identity and password primitives."""

import string

from hypothesis import given
from hypothesis import strategies as st

from verboflex.auth.identity import normalize_email

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
