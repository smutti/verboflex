"""Contracts for short-lived signed access authority."""

from datetime import UTC, datetime
from uuid import uuid4

import jwt

from verboflex.auth.access_tokens import issue_access_token
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
