"""Contracts for short-lived signed access authority."""

from datetime import UTC, datetime
from uuid import uuid4

import jwt

from verboflex.auth.access_tokens import decode_access_token, issue_access_token
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
