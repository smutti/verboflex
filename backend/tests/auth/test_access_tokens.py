"""Contracts for short-lived signed access authority."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import jwt
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import SecretStr

from verboflex.auth.access_tokens import (
    CLOCK_SKEW_TOLERANCE_SECONDS,
    COMMON_REQUIRED_CLAIMS,
    INVALID_ACCESS_TOKEN_MESSAGE,
    ORDINARY_SESSION_REQUIRED_MESSAGE,
    PASSWORD_CHANGE_REQUIRED_MESSAGE,
    PASSWORD_CHANGE_SESSION_FORBIDDEN_MESSAGE,
    InvalidAccessToken,
    PasswordChangeRequired,
    TokenPurpose,
    _claims_from_payload,
    _validated_datetime,
    _validated_purpose,
    _validated_session_id,
    _validated_token_version,
    decode_access_token,
    issue_access_token,
)
from verboflex.core.config import Settings

SIGNING_SECRET = "0123456789abcdef" * 2


def token_settings() -> Settings:
    """Return explicit local signing settings without consulting ambient env."""
    return Settings(
        jwt_secret_key=SecretStr(SIGNING_SECRET),
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


@pytest.mark.parametrize(
    ("purpose", "session_id", "expected_message"),
    [
        ("access", None, ORDINARY_SESSION_REQUIRED_MESSAGE),
        ("password_change", uuid4(), PASSWORD_CHANGE_SESSION_FORBIDDEN_MESSAGE),
    ],
)
def test_issuer_rejects_purpose_session_mismatches(
    purpose: TokenPurpose,
    session_id: UUID | None,
    expected_message: str,
) -> None:
    """Refuse to mint authority whose session shape contradicts its purpose."""
    with pytest.raises(ValueError) as error:
        issue_access_token(
            user_id=uuid4(),
            session_id=session_id,
            token_version=0,
            purpose=purpose,
            settings=token_settings(),
        )
    assert error.value.args == (expected_message,)


@pytest.mark.parametrize(
    ("operation", "expected_exception", "expected_message"),
    [
        (
            lambda: _validated_purpose({"purpose": "unapproved"}, "access"),
            InvalidAccessToken,
            INVALID_ACCESS_TOKEN_MESSAGE,
        ),
        (
            lambda: _validated_purpose({"purpose": "password_change"}, "access"),
            PasswordChangeRequired,
            PASSWORD_CHANGE_REQUIRED_MESSAGE,
        ),
        (
            lambda: _validated_purpose({"purpose": "access"}, "password_change"),
            InvalidAccessToken,
            INVALID_ACCESS_TOKEN_MESSAGE,
        ),
        (
            lambda: _validated_token_version({"token_version": True}),
            InvalidAccessToken,
            INVALID_ACCESS_TOKEN_MESSAGE,
        ),
        (
            lambda: _validated_session_id({"sid": str(uuid4())}, "password_change"),
            InvalidAccessToken,
            INVALID_ACCESS_TOKEN_MESSAGE,
        ),
        (
            lambda: _validated_session_id({}, "access"),
            InvalidAccessToken,
            INVALID_ACCESS_TOKEN_MESSAGE,
        ),
        (
            lambda: _validated_datetime({"iat": "not-a-timestamp"}, "iat"),
            InvalidAccessToken,
            INVALID_ACCESS_TOKEN_MESSAGE,
        ),
    ],
)
def test_token_validators_preserve_exact_denial_semantics(
    operation: Any,
    expected_exception: type[Exception],
    expected_message: str,
) -> None:
    """Keep purpose, session, version, and timestamp denials exact and typed."""
    with pytest.raises(expected_exception) as error:
        operation()
    assert error.value.args == (expected_message,)


def test_payload_and_decoder_failures_preserve_exact_invalid_token_semantics() -> None:
    """Translate lifetime, signature, and claim failures to one exact denial."""
    issued_at = datetime.now(UTC).replace(microsecond=0)
    payload: dict[str, object] = {
        "sub": str(uuid4()),
        "sid": str(uuid4()),
        "iat": int(issued_at.timestamp()),
        "exp": int(issued_at.timestamp()) + 901,
        "purpose": "access",
        "token_version": 0,
    }
    with pytest.raises(InvalidAccessToken) as lifetime_error:
        _claims_from_payload(payload, settings=token_settings(), expected_purpose="access")
    assert lifetime_error.value.args == (INVALID_ACCESS_TOKEN_MESSAGE,)

    with pytest.raises(InvalidAccessToken) as signature_error:
        decode_access_token("not-a-token", settings=token_settings())
    assert signature_error.value.args == (INVALID_ACCESS_TOKEN_MESSAGE,)

    payload["exp"] = int(issued_at.timestamp()) + 900
    payload["sub"] = "not-a-uuid"
    malformed = jwt.encode(payload, SIGNING_SECRET, algorithm="HS256")
    with pytest.raises(InvalidAccessToken) as claim_error:
        decode_access_token(malformed, settings=token_settings())
    assert claim_error.value.args == (INVALID_ACCESS_TOKEN_MESSAGE,)


def test_non_string_subject_is_rejected_before_uuid_coercion() -> None:
    """Reject signed claim types that cannot represent the canonical UUID subject."""
    issued_at = datetime.now(UTC).replace(microsecond=0)
    payload: dict[str, object] = {
        "sub": 42,
        "sid": str(uuid4()),
        "iat": int(issued_at.timestamp()),
        "exp": int(issued_at.timestamp()) + 900,
        "purpose": "access",
        "token_version": 0,
    }

    with pytest.raises(InvalidAccessToken) as error:
        _claims_from_payload(payload, settings=token_settings(), expected_purpose="access")

    assert error.value.args == (INVALID_ACCESS_TOKEN_MESSAGE,)


def test_issuer_and_decoder_fail_closed_without_a_signing_secret() -> None:
    """Never mint or trust bearer authority when signing material is absent."""
    unsigned_settings = Settings(jwt_secret_key=None, refresh_cookie_secure=False)

    with pytest.raises(RuntimeError, match="JWT signing secret is not configured"):
        issue_access_token(
            user_id=uuid4(),
            session_id=uuid4(),
            token_version=0,
            purpose="access",
            settings=unsigned_settings,
        )
    with pytest.raises(RuntimeError, match="JWT signing secret is not configured"):
        decode_access_token("irrelevant", settings=unsigned_settings)


def test_jwt_library_receives_the_explicit_approved_security_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin HS256, required claims, and clock tolerance at the library boundary."""
    original_encode = cast(Any, jwt.encode)
    original_decode = cast(Any, jwt.decode)
    encode_kwargs: dict[str, object] = {}
    decode_kwargs: dict[str, object] = {}

    def observe_encode(*args: object, **kwargs: object) -> str:
        encode_kwargs.update(kwargs)
        return cast(str, original_encode(*args, **kwargs))

    def observe_decode(*args: object, **kwargs: object) -> dict[str, object]:
        decode_kwargs.update(kwargs)
        return cast(dict[str, object], original_decode(*args, **kwargs))

    monkeypatch.setattr(jwt, "encode", observe_encode)
    token = issue_access_token(
        user_id=uuid4(),
        session_id=uuid4(),
        token_version=0,
        purpose="access",
        settings=token_settings(),
    )
    monkeypatch.setattr(jwt, "decode", observe_decode)

    decode_access_token(token, settings=token_settings())

    assert encode_kwargs["algorithm"] == "HS256"
    assert decode_kwargs["algorithms"] == ["HS256"]
    assert decode_kwargs["options"] == {"require": list(COMMON_REQUIRED_CLAIMS)}
    assert decode_kwargs["leeway"] == CLOCK_SKEW_TOLERANCE_SECONDS


def test_issuer_requests_an_explicit_utc_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default issuance must not depend on the host's local timezone."""
    observed_timezones: list[object] = []
    issued_at = datetime.now(UTC).replace(microsecond=0)

    class ObservedDateTime(datetime):
        @classmethod
        def now(cls, timezone: object = None) -> ObservedDateTime:
            observed_timezones.append(timezone)
            return cls.fromtimestamp(issued_at.timestamp(), UTC)

    monkeypatch.setattr("verboflex.auth.access_tokens.datetime", ObservedDateTime)

    token = issue_access_token(
        user_id=uuid4(),
        session_id=uuid4(),
        token_version=0,
        purpose="access",
        settings=token_settings(),
    )

    assert observed_timezones == [UTC]
    assert jwt.decode(token, SIGNING_SECRET, algorithms=["HS256"])["iat"] == int(
        issued_at.timestamp()
    )


@pytest.mark.parametrize(("expired_seconds", "accepted"), [(2, True), (7, False)])
def test_expiry_clock_skew_is_bounded_to_five_seconds(
    expired_seconds: int,
    accepted: bool,
) -> None:
    """Accept only the documented five-second network clock tolerance."""
    expires_at = datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=expired_seconds)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "sid": str(uuid4()),
            "iat": int(expires_at.timestamp()) - 900,
            "exp": int(expires_at.timestamp()),
            "purpose": "access",
            "token_version": 0,
        },
        SIGNING_SECRET,
        algorithm="HS256",
    )

    if accepted:
        assert decode_access_token(token, settings=token_settings()).expires_at == expires_at
    else:
        with pytest.raises(InvalidAccessToken):
            decode_access_token(token, settings=token_settings())


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


@pytest.mark.parametrize(
    "malformation",
    [
        "unknown-purpose",
        "boolean-version",
        "negative-version",
        "ordinary-without-session",
        "password-change-with-session",
        "invalid-user-id",
    ],
)
def test_signed_but_malformed_authority_fails_closed(malformation: str) -> None:
    """A valid signature cannot redeem contradictory or ill-typed authority."""
    issued_at = datetime.now(UTC).replace(microsecond=0)
    payload: dict[str, str | int | bool] = {
        "sub": str(uuid4()),
        "sid": str(uuid4()),
        "iat": int(issued_at.timestamp()),
        "exp": int(issued_at.timestamp()) + 900,
        "purpose": "access",
        "token_version": 0,
    }
    expected_purpose: TokenPurpose = "access"
    if malformation == "unknown-purpose":
        payload["purpose"] = "unapproved"
    elif malformation == "boolean-version":
        payload["token_version"] = True
    elif malformation == "negative-version":
        payload["token_version"] = -1
    elif malformation == "ordinary-without-session":
        del payload["sid"]
    elif malformation == "password-change-with-session":
        payload["purpose"] = "password_change"
        payload["exp"] = int(issued_at.timestamp()) + 300
        expected_purpose = "password_change"
    else:
        payload["sub"] = "not-a-uuid"
    token = jwt.encode(payload, SIGNING_SECRET, algorithm="HS256")

    with pytest.raises(InvalidAccessToken):
        decode_access_token(
            token,
            settings=token_settings(),
            expected_purpose=expected_purpose,
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
