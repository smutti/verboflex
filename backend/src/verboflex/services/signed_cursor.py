"""One closed, bounded HMAC authority for private keyset cursors."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

MAX_SIGNED_CURSOR_CHARS = 2048
MAX_CURSOR_SCOPE_CHARS = 512
MAX_CURSOR_FILTER_BYTES = 1024
MAX_CURSOR_PAGE_SIZE = 100
MAX_CURSOR_VERSION = 2_147_483_647

CursorCollectionKind = Literal["search", "activity", "comments", "notifications"]
CursorDirection = Literal["ascending", "descending"]

_COLLECTION_KINDS = frozenset(("search", "activity", "comments", "notifications"))
_DIRECTIONS = frozenset(("ascending", "descending"))
_SIGNED_CURSOR_KEYS = frozenset(
    ("direction", "filters", "kind", "last", "page_size", "principal", "scope", "v")
)


class InvalidSignedCursor(ValueError):
    """The single non-disclosing failure for an untrusted signed cursor."""


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("value is not canonical JSON") from error


def _filter_digest(filters: Mapping[str, object]) -> str:
    if not isinstance(filters, Mapping) or any(type(key) is not str for key in filters):
        raise ValueError("invalid cursor binding")
    canonical_filters = _canonical_json_bytes(dict(filters))
    if len(canonical_filters) > MAX_CURSOR_FILTER_BYTES:
        raise ValueError("invalid cursor binding")
    return hashlib.sha256(canonical_filters).hexdigest()


def _canonical_timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("invalid cursor position")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_canonical_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError
    parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    if _canonical_timestamp(parsed) != value:
        raise ValueError
    return parsed


def _parse_canonical_uuid(value: object) -> UUID:
    if not isinstance(value, str):
        raise ValueError
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError
    return parsed


@dataclass(frozen=True, slots=True)
class CursorBinding:
    """Exact caller, collection, scope, filters, and page contract."""

    kind: CursorCollectionKind
    principal_id: UUID
    scope: str
    filters: Mapping[str, object]
    page_size: int
    direction: CursorDirection = "descending"
    version: int = 1

    def __post_init__(self) -> None:
        try:
            if self.kind not in _COLLECTION_KINDS:
                raise ValueError
            if not isinstance(self.principal_id, UUID):
                raise ValueError
            if type(self.scope) is not str or not 1 <= len(self.scope) <= MAX_CURSOR_SCOPE_CHARS:
                raise ValueError
            if type(self.page_size) is not int or not 1 <= self.page_size <= MAX_CURSOR_PAGE_SIZE:
                raise ValueError
            if self.direction not in _DIRECTIONS:
                raise ValueError
            if type(self.version) is not int or not 1 <= self.version <= MAX_CURSOR_VERSION:
                raise ValueError
            _filter_digest(self.filters)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("invalid cursor binding") from error


@dataclass(frozen=True, slots=True)
class CursorPosition:
    """Stable newest/oldest keyset boundary with a UUID tie-breaker."""

    created_at: datetime
    id: UUID

    def __post_init__(self) -> None:
        try:
            canonical_created_at = _canonical_timestamp(self.created_at)
            if not isinstance(self.id, UUID):
                raise ValueError
            object.__setattr__(self, "created_at", _parse_canonical_timestamp(canonical_created_at))
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("invalid cursor position") from error


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    if type(value) is not str or not value:
        raise ValueError
    decoded = base64.b64decode(
        value + "=" * (-len(value) % 4),
        altchars=b"-_",
        validate=True,
    )
    if _b64encode(decoded) != value:
        raise ValueError
    return decoded


class SignedCursorCodec:
    """Canonical JSON/base64 signing plus typed private keyset bindings."""

    def __init__(
        self,
        secret: str,
        *,
        max_cursor_chars: int = MAX_SIGNED_CURSOR_CHARS,
    ) -> None:
        if type(secret) is not str or not secret:
            raise ValueError("cursor signing secret is required")
        if (
            type(max_cursor_chars) is not int
            or not 1 <= max_cursor_chars <= MAX_SIGNED_CURSOR_CHARS
        ):
            raise ValueError("invalid cursor wire bound")
        self._secret = secret.encode("utf-8")
        self._max_cursor_chars = max_cursor_chars

    def encode_payload(self, payload: Mapping[str, object]) -> str:
        """Sign a canonical closed payload without introducing another wire codec."""
        if not isinstance(payload, Mapping):
            raise ValueError("invalid cursor payload")
        body = _canonical_json_bytes(dict(payload))
        signature = hmac.digest(self._secret, body, "sha256")
        token = f"{_b64encode(body)}.{_b64encode(signature)}"
        if len(token) > self._max_cursor_chars:
            raise ValueError("cursor payload exceeds its wire bound")
        return token

    def decode_payload(
        self,
        token: str,
        *,
        required_keys: frozenset[str] | None = None,
    ) -> dict[str, object]:
        """Verify signature/canonical encoding before returning a bounded JSON object."""
        try:
            if type(token) is not str or not 1 <= len(token) <= self._max_cursor_chars:
                raise ValueError
            segments = token.split(".")
            if len(segments) != 2:
                raise ValueError
            body = _b64decode(segments[0])
            signature = _b64decode(segments[1])
            if len(signature) != hashlib.sha256().digest_size:
                raise ValueError
            expected_signature = hmac.digest(self._secret, body, "sha256")
            if not hmac.compare_digest(signature, expected_signature):
                raise ValueError
            payload = json.loads(body)
            if not isinstance(payload, dict) or any(type(key) is not str for key in payload):
                # JSON object decoding cannot produce non-string keys; retain the invariant.
                raise ValueError  # pragma: no cover
            if _canonical_json_bytes(payload) != body:
                raise ValueError
            if required_keys is not None and frozenset(payload) != required_keys:
                raise ValueError
            return cast(dict[str, object], payload)
        except (
            binascii.Error,
            json.JSONDecodeError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
        ):
            raise InvalidSignedCursor("invalid cursor") from None

    def encode(self, *, binding: CursorBinding, position: CursorPosition) -> str:
        """Encode the complete typed authority for a private bounded collection."""
        payload: dict[str, object] = {
            "direction": binding.direction,
            "filters": _filter_digest(binding.filters),
            "kind": binding.kind,
            "last": [_canonical_timestamp(position.created_at), str(position.id)],
            "page_size": binding.page_size,
            "principal": str(binding.principal_id),
            "scope": binding.scope,
            "v": binding.version,
        }
        return self.encode_payload(payload)

    def decode(self, token: str, *, binding: CursorBinding) -> CursorPosition:
        """Decode only when every expected binding dimension matches exactly."""
        try:
            payload = self.decode_payload(token, required_keys=_SIGNED_CURSOR_KEYS)
            expected = {
                "direction": binding.direction,
                "filters": _filter_digest(binding.filters),
                "kind": binding.kind,
                "page_size": binding.page_size,
                "principal": str(binding.principal_id),
                "scope": binding.scope,
                "v": binding.version,
            }
            if any(payload.get(key) != value for key, value in expected.items()):
                raise ValueError
            if payload["kind"] not in _COLLECTION_KINDS:
                # Exact equality with a validated binding kind makes this defensive only.
                raise ValueError  # pragma: no cover
            if type(payload["page_size"]) is not int or type(payload["v"]) is not int:
                raise ValueError
            last = payload["last"]
            if not isinstance(last, list) or len(last) != 2:
                raise ValueError
            return CursorPosition(
                created_at=_parse_canonical_timestamp(last[0]),
                id=_parse_canonical_uuid(last[1]),
            )
        except InvalidSignedCursor, TypeError, ValueError, OverflowError:
            raise InvalidSignedCursor("invalid cursor") from None


def encode_signed_cursor(
    *,
    binding: CursorBinding,
    position: CursorPosition,
    secret: str,
) -> str:
    """Encode one typed cursor through the shared authority."""
    return SignedCursorCodec(secret).encode(binding=binding, position=position)


def decode_signed_cursor(
    token: str,
    *,
    binding: CursorBinding,
    secret: str,
) -> CursorPosition:
    """Decode one typed cursor through the shared authority."""
    return SignedCursorCodec(secret).decode(token, binding=binding)
