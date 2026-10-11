"""Adversarial contract for the shared signed keyset cursor authority."""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
from datetime import UTC, datetime
from types import ModuleType
from uuid import UUID

import pytest

MODULE_NAME = "verboflex.services.signed_cursor"
CURSOR_SECRET = "shared-cursor-test-secret-at-least-32-bytes"
PRINCIPAL_ID = UUID("10000000-0000-4000-8000-0000000000ab")
POSITION_ID = UUID("20000000-0000-4000-8000-0000000000cd")
CREATED_AT = datetime(2026, 9, 9, 12, 34, 56, 123456, tzinfo=UTC)


def _load_module() -> ModuleType:
    specification = importlib.util.find_spec(MODULE_NAME)
    assert specification is not None, "shared signed cursor module is not implemented"
    module = __import__(MODULE_NAME, fromlist=["*"])
    assert isinstance(module, ModuleType)
    return module


def _binding(**changes: object) -> object:
    module = _load_module()
    values: dict[str, object] = {
        "kind": "comments",
        "principal_id": PRINCIPAL_ID,
        "scope": "translation-group:30000000-0000-4000-8000-000000000003:it",
        "filters": {"anchor": None, "include_removed": False},
        "page_size": 20,
        "direction": "descending",
        "version": 1,
    }
    values.update(changes)
    return module.CursorBinding(**values)


def _position(**changes: object) -> object:
    module = _load_module()
    values: dict[str, object] = {"created_at": CREATED_AT, "id": POSITION_ID}
    values.update(changes)
    return module.CursorPosition(**values)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _signed_payload(payload: dict[str, object], *, canonical: bool = True) -> str:
    if canonical:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    else:
        body = json.dumps(payload, sort_keys=False, indent=1).encode()
    signature = hmac.digest(CURSOR_SECRET.encode(), body, "sha256")
    return f"{_b64encode(body)}.{_b64encode(signature)}"


def _decode_payload(token: str) -> dict[str, object]:
    encoded_body = token.split(".", 1)[0]
    body = base64.urlsafe_b64decode(encoded_body + "=" * (-len(encoded_body) % 4))
    payload = json.loads(body)
    assert isinstance(payload, dict)
    return payload


def test_shared_cursor_module_and_public_symbols_exist() -> None:
    module = _load_module()
    for name in (
        "CursorBinding",
        "CursorPosition",
        "SignedCursorCodec",
        "encode_signed_cursor",
        "decode_signed_cursor",
    ):
        assert hasattr(module, name)


def test_round_trip_uses_canonical_timestamp_and_uuid_position() -> None:
    module = _load_module()
    binding = _binding()
    position = _position()
    token = module.encode_signed_cursor(
        binding=binding,
        position=position,
        secret=CURSOR_SECRET,
    )

    assert (
        module.decode_signed_cursor(
            token,
            binding=binding,
            secret=CURSOR_SECRET,
        )
        == position
    )
    payload = _decode_payload(token)
    assert payload["last"] == ["2026-09-09T12:34:56.123456Z", str(POSITION_ID)]


def test_equal_timestamp_positions_retain_uuid_tie_breaker() -> None:
    module = _load_module()
    binding = _binding()
    lower = _position(id=UUID("20000000-0000-4000-8000-000000000001"))
    higher = _position(id=UUID("20000000-0000-4000-8000-000000000002"))

    lower_token = module.encode_signed_cursor(binding=binding, position=lower, secret=CURSOR_SECRET)
    higher_token = module.encode_signed_cursor(
        binding=binding, position=higher, secret=CURSOR_SECRET
    )

    assert module.decode_signed_cursor(lower_token, binding=binding, secret=CURSOR_SECRET) == lower
    assert (
        module.decode_signed_cursor(higher_token, binding=binding, secret=CURSOR_SECRET) == higher
    )
    assert lower.id < higher.id


def test_exact_hmac_canonical_json_and_unpadded_base64_contract() -> None:
    module = _load_module()
    binding = _binding()
    position = _position()
    token = module.encode_signed_cursor(binding=binding, position=position, secret=CURSOR_SECRET)
    payload = _decode_payload(token)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    expected = (
        f"{_b64encode(body)}.{_b64encode(hmac.digest(CURSOR_SECRET.encode(), body, 'sha256'))}"
    )

    assert token == expected
    assert token.count(".") == 1
    assert "=" not in token
    assert payload == {
        "direction": "descending",
        "filters": hashlib.sha256(b'{"anchor":null,"include_removed":false}').hexdigest(),
        "kind": "comments",
        "last": ["2026-09-09T12:34:56.123456Z", str(POSITION_ID)],
        "page_size": 20,
        "principal": str(PRINCIPAL_ID),
        "scope": "translation-group:30000000-0000-4000-8000-000000000003:it",
        "v": 1,
    }


@pytest.mark.parametrize(
    "change",
    [
        {"principal_id": UUID("10000000-0000-4000-8000-000000000099")},
        {"kind": "activity"},
        {"kind": "notifications"},
        {"kind": "search"},
        {"scope": "translation-group:foreign:it"},
        {"filters": {"anchor": "different", "include_removed": False}},
        {"page_size": 25},
        {"direction": "ascending"},
        {"version": 2},
    ],
    ids=[
        "principal",
        "activity-kind",
        "notification-kind",
        "search-kind",
        "scope",
        "filters",
        "page-size",
        "direction",
        "version",
    ],
)
def test_decode_rejects_every_mismatched_binding(change: dict[str, object]) -> None:
    module = _load_module()
    token = module.encode_signed_cursor(
        binding=_binding(), position=_position(), secret=CURSOR_SECRET
    )

    with pytest.raises(module.InvalidSignedCursor, match=r"^invalid cursor$"):
        module.decode_signed_cursor(
            token,
            binding=_binding(**change),
            secret=CURSOR_SECRET,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-field",
        "extra-field",
        "last-not-list",
        "last-count",
        "timestamp-not-string",
        "timestamp-noncanonical",
        "timestamp-naive",
        "uuid-not-string",
        "uuid-uppercase",
        "uuid-invalid",
        "page-size-bool",
        "version-bool",
        "filters-not-digest",
        "principal-noncanonical",
        "kind-unknown",
    ],
)
def test_signed_noncanonical_or_nonclosed_payloads_fail_generically(mutation: str) -> None:
    module = _load_module()
    binding = _binding()
    valid = module.encode_signed_cursor(binding=binding, position=_position(), secret=CURSOR_SECRET)
    payload = _decode_payload(valid)
    if mutation == "missing-field":
        payload.pop("scope")
    elif mutation == "extra-field":
        payload["decoded_secret"] = "do-not-leak"
    elif mutation == "last-not-list":
        payload["last"] = {}
    elif mutation == "last-count":
        payload["last"] = payload["last"][:1]  # type: ignore[index]
    elif mutation == "timestamp-not-string":
        payload["last"][0] = 1  # type: ignore[index]
    elif mutation == "timestamp-noncanonical":
        payload["last"][0] = "2026-09-09T12:34:56.123456+00:00"  # type: ignore[index]
    elif mutation == "timestamp-naive":
        payload["last"][0] = "2026-09-09T12:34:56.123456"  # type: ignore[index]
    elif mutation == "uuid-not-string":
        payload["last"][1] = 2  # type: ignore[index]
    elif mutation == "uuid-uppercase":
        payload["last"][1] = str(POSITION_ID).upper()  # type: ignore[index]
    elif mutation == "uuid-invalid":
        payload["last"][1] = "not-a-uuid"  # type: ignore[index]
    elif mutation == "page-size-bool":
        payload["page_size"] = True
    elif mutation == "version-bool":
        payload["v"] = True
    elif mutation == "filters-not-digest":
        payload["filters"] = {"anchor": None}
    elif mutation == "principal-noncanonical":
        payload["principal"] = str(PRINCIPAL_ID).upper()
    elif mutation == "kind-unknown":
        payload["kind"] = "private-history"

    token = _signed_payload(payload)
    with pytest.raises(module.InvalidSignedCursor, match=r"^invalid cursor$") as captured:
        module.decode_signed_cursor(token, binding=binding, secret=CURSOR_SECRET)
    assert "do-not-leak" not in str(captured.value)


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda valid: "",
        lambda valid: "x" * 2049,
        lambda valid: valid + ".extra",
        lambda valid: valid.replace(".", "=.", 1),
        lambda valid: "!" + valid[1:],
        lambda valid: valid[:-1] + ("A" if valid[-1] != "A" else "B"),
    ],
    ids=["empty", "oversized", "extra-segment", "padded", "invalid-base64", "tamper"],
)
def test_malformed_wire_tokens_fail_generically(token_factory) -> None:
    module = _load_module()
    binding = _binding()
    valid = module.encode_signed_cursor(binding=binding, position=_position(), secret=CURSOR_SECRET)

    with pytest.raises(module.InvalidSignedCursor, match=r"^invalid cursor$"):
        module.decode_signed_cursor(
            token_factory(valid),
            binding=binding,
            secret=CURSOR_SECRET,
        )


def test_signed_but_noncanonical_json_is_rejected() -> None:
    module = _load_module()
    binding = _binding()
    valid = module.encode_signed_cursor(binding=binding, position=_position(), secret=CURSOR_SECRET)
    noncanonical = _signed_payload(_decode_payload(valid), canonical=False)

    with pytest.raises(module.InvalidSignedCursor, match=r"^invalid cursor$"):
        module.decode_signed_cursor(noncanonical, binding=binding, secret=CURSOR_SECRET)


@pytest.mark.parametrize(
    "values",
    [
        {"kind": "unknown"},
        {"principal_id": "not-a-uuid"},
        {"scope": ""},
        {"scope": "x" * 513},
        {"filters": {"bad": float("nan")}},
        {"filters": {"nested": object()}},
        {"page_size": True},
        {"page_size": 0},
        {"page_size": 101},
        {"direction": "sideways"},
        {"version": True},
        {"version": 0},
    ],
)
def test_invalid_binding_fails_before_token_work(values: dict[str, object]) -> None:
    _load_module()
    with pytest.raises(ValueError, match="invalid cursor binding"):
        _binding(**values)


@pytest.mark.parametrize(
    "values",
    [
        {"created_at": datetime(2026, 9, 9, 12, 34, 56)},
        {"created_at": "2026-09-09T12:34:56Z"},
        {"id": "not-a-uuid"},
    ],
)
def test_invalid_position_is_rejected(values: dict[str, object]) -> None:
    _load_module()
    with pytest.raises(ValueError, match="invalid cursor position"):
        _position(**values)


@pytest.mark.parametrize(
    "filters",
    [
        {1: "non-string-key"},
        {"oversized": "x" * 2_000},
    ],
)
def test_filter_binding_rejects_non_string_keys_and_oversized_canonical_json(
    filters: dict[object, object],
) -> None:
    with pytest.raises(ValueError, match="invalid cursor binding"):
        _binding(filters=filters)


def test_timestamp_parser_rejects_parseable_but_noncanonical_precision() -> None:
    module = _load_module()
    with pytest.raises(ValueError):
        module._parse_canonical_timestamp("2026-09-09T12:34:56Z")


@pytest.mark.parametrize(
    ("secret", "maximum", "message"),
    [
        ("", 100, "secret"),
        (CURSOR_SECRET, True, "wire bound"),
        (CURSOR_SECRET, 0, "wire bound"),
        (CURSOR_SECRET, 2_049, "wire bound"),
    ],
)
def test_codec_constructor_rejects_missing_secret_and_inexact_wire_bounds(
    secret: object, maximum: object, message: str
) -> None:
    module = _load_module()
    with pytest.raises(ValueError, match=message):
        module.SignedCursorCodec(secret, max_cursor_chars=maximum)


def test_raw_payload_encoder_rejects_non_mapping_and_oversized_token() -> None:
    module = _load_module()
    codec = module.SignedCursorCodec(CURSOR_SECRET, max_cursor_chars=20)
    with pytest.raises(ValueError, match="payload"):
        codec.encode_payload([])
    with pytest.raises(ValueError, match="wire bound"):
        codec.encode_payload({"bounded": "but-too-large-for-this-codec"})


@pytest.mark.parametrize("value", [None, "", "YQ=="])
def test_private_base64_decoder_rejects_non_string_empty_and_padded_values(value: object) -> None:
    module = _load_module()
    with pytest.raises(ValueError):
        module._b64decode(value)
