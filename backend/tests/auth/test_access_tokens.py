"""Contracts for short-lived signed access authority."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from hypothesis import given
from hypothesis import strategies as st

from verboflex.auth.access_tokens import (
    InvalidAccessToken,
    PasswordChangeRequired,
    decode_access_token,
    issue_access_token,
)
from verboflex.core.config import Settings

SIGNING_SECRET = "0123456789abcdef" * 2


def token_settings() -> Settings:
    """Return explicit local signing settings without consulting ambient env."""
    return Settings(
        jwt_secret_key=SIGNING_SECRET,
        refresh_cookie_secure=False,
    )


def test_ordinary_access_token_has_exact_authority_and_fifteen_minute_lifetime() -> None:
    """Issue the complete ordinary claim set with an exact 900-second lifetime."""
    user_id = uuid4()
    session_id = uuid4()
    issued_at = datetime.now(UTC).replace(microsecond=0)

    token = issue_access_token(
        user_id=user_id,
        session_id=session_id,
        token_version=7,
        purpose="access",
        settings=token_settings(),
        now=issued_at,
    )

    payload = jwt.decode(token, SIGNING_SECRET, algorithms=["HS256"])
    assert payload == {
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": int(issued_at.timestamp()),
        "exp": int(issued_at.timestamp()) + 900,
        "purpose": "access",
        "token_version": 7,
    }


def test_password_change_token_omits_session_and_expires_after_five_minutes() -> None:
    """Temporary credentials receive only sessionless five-minute authority."""
    user_id = uuid4()
    issued_at = datetime.now(UTC).replace(microsecond=0)

    token = issue_access_token(
        user_id=user_id,
        token_version=3,
        purpose="password_change",
        settings=token_settings(),
        now=issued_at,
    )

    payload = jwt.decode(token, SIGNING_SECRET, algorithms=["HS256"])
    assert payload == {
        "sub": str(user_id),
        "iat": int(issued_at.timestamp()),
        "exp": int(issued_at.timestamp()) + 300,
        "purpose": "password_change",
        "token_version": 3,
    }


def test_ordinary_access_token_round_trips_through_strict_verification() -> None:
    """Verify the signature, required claims, UUIDs, purpose, and timestamps."""
    user_id = uuid4()
    session_id = uuid4()
    issued_at = datetime.now(UTC).replace(microsecond=0)
    token = issue_access_token(
        user_id=user_id,
        session_id=session_id,
        token_version=11,
        purpose="access",
        settings=token_settings(),
        now=issued_at,
    )

    claims = decode_access_token(token, settings=token_settings())

    assert claims.user_id == user_id
    assert claims.session_id == session_id
    assert claims.issued_at == issued_at
    assert claims.expires_at.timestamp() - claims.issued_at.timestamp() == 900
    assert claims.purpose == "access"
    assert claims.token_version == 11


def test_signature_tampering_is_rejected_as_invalid_authority() -> None:
    """Never accept a caller-modified signature under the configured HS256 key."""
    token = issue_access_token(
        user_id=uuid4(),
        session_id=uuid4(),
        token_version=0,
        purpose="access",
        settings=token_settings(),
    )
    header, payload, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    tampered = ".".join((header, payload, replacement + signature[1:]))

    with pytest.raises(InvalidAccessToken):
        decode_access_token(tampered, settings=token_settings())


def test_expired_access_token_is_rejected_as_invalid_authority() -> None:
    """Expiry validation remains active and uses only the configured tolerance."""
    issued_at = datetime.now(UTC) - timedelta(minutes=20)
    expired = issue_access_token(
        user_id=uuid4(),
        session_id=uuid4(),
        token_version=0,
        purpose="access",
        settings=token_settings(),
        now=issued_at,
    )

    with pytest.raises(InvalidAccessToken):
        decode_access_token(expired, settings=token_settings())


def test_missing_required_claim_is_rejected_as_invalid_authority() -> None:
    """A signed token is still invalid when any authority dimension is absent."""
    now = datetime.now(UTC)
    incomplete = jwt.encode(
        {
            "sub": str(uuid4()),
            "sid": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
            "purpose": "access",
        },
        SIGNING_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(InvalidAccessToken):
        decode_access_token(incomplete, settings=token_settings())


def test_password_change_authority_is_denied_from_an_ordinary_resource() -> None:
    """Translate restricted purpose to the dedicated 403 authorization seam."""
    restricted = issue_access_token(
        user_id=uuid4(),
        token_version=0,
        purpose="password_change",
        settings=token_settings(),
    )

    with pytest.raises(PasswordChangeRequired):
        decode_access_token(restricted, settings=token_settings())


def test_ordinary_authority_is_invalid_for_password_change_only_access() -> None:
    """Ordinary sessions cannot be relabeled as password-change authority."""
    ordinary = issue_access_token(
        user_id=uuid4(),
        session_id=uuid4(),
        token_version=0,
        purpose="access",
        settings=token_settings(),
    )

    with pytest.raises(InvalidAccessToken):
        decode_access_token(
            ordinary,
            settings=token_settings(),
            expected_purpose="password_change",
        )


@given(extra_seconds=st.integers(min_value=1, max_value=3600))
def test_generated_overlong_expiry_windows_fail_closed(extra_seconds: int) -> None:
    """Signed claims cannot extend ordinary authority past the approved lifetime."""
    issued_at = datetime.now(UTC).replace(microsecond=0)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "sid": str(uuid4()),
            "iat": int(issued_at.timestamp()),
            "exp": int(issued_at.timestamp()) + 900 + extra_seconds,
            "purpose": "access",
            "token_version": 0,
        },
        SIGNING_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(InvalidAccessToken):
        decode_access_token(token, settings=token_settings())
