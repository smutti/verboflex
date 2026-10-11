"""Immutable write authority and a bounded original-coordinate byte splice kernel."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from verboflex.localization.importing.core import (
    MAX_CANONICAL_FILE_BYTES,
    MAX_CANONICAL_PATH_LENGTH,
    MAX_CANONICAL_TEXT_LENGTH,
    MAX_CANONICAL_VALUES,
    CanonicalLocator,
    CanonicalParserInput,
    CanonicalSelector,
    RepositorySide,
)
from verboflex.localization.preview.core import normalize_preview_locale


class WritebackReason(StrEnum):
    STALE_BASIS = "stale_basis"
    SOURCE_BRANCH_CHANGED = "source_branch_changed"
    SOURCE_FILE_CHANGED = "source_file_changed"
    SOURCE_FILE_MISSING = "source_file_missing"
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNSUPPORTED_SHAPE = "unsupported_shape"
    UNSUPPORTED_FILE_ATTRIBUTES = "unsupported_file_attributes"
    AMBIGUOUS_LOCATOR = "ambiguous_locator"
    INVALID_REPLACEMENT = "invalid_replacement"
    LIMIT_EXCEEDED = "limit_exceeded"
    INVALID_OUTPUT = "invalid_output"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    AUTHORITY_UNAVAILABLE = "authority_unavailable"
    UNSUPPORTED_PROVIDER = "unsupported_provider"


_MESSAGES = {
    WritebackReason.STALE_BASIS: "The selected changes need review against their current import.",
    WritebackReason.SOURCE_BRANCH_CHANGED: "The source branch changed. Refresh and review.",
    WritebackReason.SOURCE_FILE_CHANGED: "The source file changed. Refresh and review the changes.",
    WritebackReason.SOURCE_FILE_MISSING: "The original file is unavailable. Refresh the mapping.",
    WritebackReason.UNSUPPORTED_FORMAT: "This format cannot be written back in this version.",
    WritebackReason.UNSUPPORTED_SHAPE: "This structure cannot be modified safely in this version.",
    WritebackReason.UNSUPPORTED_FILE_ATTRIBUTES: "This source is not a verified regular text file.",
    WritebackReason.AMBIGUOUS_LOCATOR: "The selected values do not identify distinct locations.",
    WritebackReason.INVALID_REPLACEMENT: "The proposed text cannot be represented safely.",
    WritebackReason.LIMIT_EXCEEDED: "The changes exceed supported file or batch limits.",
    WritebackReason.INVALID_OUTPUT: "The modified file did not pass preservation checks.",
    WritebackReason.PROVIDER_UNAVAILABLE: "The repository could not be checked. Try again later.",
    WritebackReason.AUTHORITY_UNAVAILABLE: "Account or repository authority is unavailable.",
    WritebackReason.UNSUPPORTED_PROVIDER: (
        "GitHub repositories support imports and local review only; "
        "remote writes are not available."
    ),
}


class WritebackRejected(ValueError):
    """Closed failure boundary: never accept provider bodies or translation text."""

    def __init__(self, reason: WritebackReason) -> None:
        if type(reason) is not WritebackReason:
            raise ValueError("invalid write-back reason")
        self.reason = reason
        super().__init__(_MESSAGES[reason])


def _integer(value: object, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _text(value: object, *, minimum: int = 0, maximum: int = MAX_CANONICAL_TEXT_LENGTH) -> bool:
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        return False
    # Surrogates cannot be represented as source Unicode under any supported codec.
    return not any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _path(value: object) -> bool:
    return (
        _text(value, minimum=1, maximum=MAX_CANONICAL_PATH_LENGTH)
        and isinstance(value, str)
        and not value.startswith("/")
        and "\\" not in value
        and all(part not in {"", ".", ".."} for part in value.split("/"))
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def _digest(value: object, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def _attributes(attributes: tuple[str, ...] | None) -> None:
    if attributes is not None and (
        type(attributes) is not tuple
        or len(attributes) > 16
        or any(not _text(item, minimum=1, maximum=64) for item in attributes)
        or len(set(attributes)) != len(attributes)
    ):
        raise WritebackRejected(WritebackReason.UNSUPPORTED_FILE_ATTRIBUTES)


@dataclass(frozen=True, slots=True)
class SourceFileAuthority:
    """Coordinates captured from one immutable import source reference."""

    import_execution_id: UUID
    source_reference_position: int
    repository_id: UUID
    repository_side: RepositorySide
    configured_branch: str
    commit_hash: str
    path: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.import_execution_id) is not UUID
            or type(self.repository_id) is not UUID
            or not _integer(self.source_reference_position, 0, 2_147_483_647)
            or self.repository_side not in ("direct", "keys", "translations")
            or not _text(self.configured_branch, minimum=1, maximum=255)
            or any(
                ord(character) < 32 or ord(character) == 127 for character in self.configured_branch
            )
            or not _digest(self.commit_hash, 40)
            or not _path(self.path)
            or not _integer(self.size_bytes, 0, MAX_CANONICAL_FILE_BYTES)
            or not _digest(self.sha256, 64)
        ):
            raise WritebackRejected(WritebackReason.STALE_BASIS)


def _verify_bytes(authority: SourceFileAuthority, content: bytes) -> None:
    if type(authority) is not SourceFileAuthority:
        raise WritebackRejected(WritebackReason.STALE_BASIS)
    if (
        type(content) is not bytes
        or len(content) != authority.size_bytes
        or hashlib.sha256(content).hexdigest() != authority.sha256
    ):
        raise WritebackRejected(WritebackReason.SOURCE_FILE_CHANGED)


@dataclass(frozen=True, slots=True)
class SourceFileSnapshot:
    authority: SourceFileAuthority
    parser_input: CanonicalParserInput = field(repr=False)
    # None is deliberately distinct from verified ordinary-file metadata ().
    attributes: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if type(self.parser_input) is not CanonicalParserInput:
            raise WritebackRejected(WritebackReason.STALE_BASIS)
        _verify_bytes(self.authority, self.parser_input.content)
        if (
            self.parser_input.path != self.authority.path
            or self.parser_input.repository_side != self.authority.repository_side
        ):
            raise WritebackRejected(WritebackReason.STALE_BASIS)
        _attributes(self.attributes)


@dataclass(frozen=True, slots=True)
class WriteEdit:
    # Qt identities can contain source sentences, so even identity metadata is private.
    logical_key: str = field(repr=False)
    language: str
    selector: CanonicalSelector = field(repr=False)
    locator: CanonicalLocator = field(repr=False)
    expected_text: str = field(repr=False)
    replacement_text: str = field(repr=False)

    def __post_init__(self) -> None:
        if (
            not _text(self.logical_key, minimum=1)
            or not _text(self.language, minimum=2, maximum=32)
            or normalize_preview_locale(self.language) != self.language
            or type(self.selector) is not CanonicalSelector
            or type(self.locator) is not CanonicalLocator
            or not _text(self.expected_text)
            or not _text(self.replacement_text)
        ):
            raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)


@dataclass(frozen=True, slots=True)
class WriteInsert:
    """An explicitly absent selector; never fabricates an imported locator."""

    logical_key: str = field(repr=False)
    language: str
    selector: CanonicalSelector = field(repr=False)
    replacement_text: str = field(repr=False)
    source_text: str = field(default="", repr=False)
    context: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if (
            not _text(self.logical_key, minimum=1, maximum=4096)
            or not _text(self.language, minimum=2, maximum=32)
            or normalize_preview_locale(self.language) != self.language
            or type(self.selector) is not CanonicalSelector
            or not _text(self.replacement_text, maximum=65536)
            or not _text(self.source_text, maximum=65536)
            or not _text(self.context, maximum=4096)
        ):
            raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)

    @property
    def expected_text(self) -> str:
        return ""


type WriteOperation = WriteEdit | WriteInsert


@dataclass(frozen=True, slots=True)
class ByteEdit:
    start: int
    end: int
    replacement: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (
            not _integer(self.start, 0, MAX_CANONICAL_FILE_BYTES)
            or not _integer(self.end, 0, MAX_CANONICAL_FILE_BYTES)
            or self.start > self.end
            or type(self.replacement) is not bytes
        ):
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        if len(self.replacement) > MAX_CANONICAL_FILE_BYTES:
            raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)


class ByteEditBuffer:
    """Bound encoded replacements while adapters construct their edit plans.

    Disjoint replacement bytes are all retained in the final file, so their sum
    cannot exceed its ceiling. Original bytes removed by *later* edits are not
    charged here: the splice kernel checks the exact final size, allowing valid
    growth/shrink cancellation independently of edit order.
    """

    def __init__(self) -> None:
        self._edits: list[ByteEdit] = []
        self._replacement_bytes = 0

    def append(self, edit: ByteEdit) -> None:
        if type(edit) is not ByteEdit:
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        size = self._replacement_bytes + len(edit.replacement)
        if len(self._edits) >= MAX_CANONICAL_VALUES or size > MAX_CANONICAL_FILE_BYTES:
            raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
        self._replacement_bytes = size
        self._edits.append(edit)

    def freeze(self) -> tuple[ByteEdit, ...]:
        return tuple(self._edits)


@dataclass(frozen=True, slots=True)
class RenderedFile:
    authority: SourceFileAuthority
    original_bytes: bytes = field(repr=False)
    content: bytes = field(repr=False)
    before_sha256: str
    after_sha256: str
    changed_edits: tuple[WriteOperation, ...] = field(repr=False)
    attributes: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        _verify_bytes(self.authority, self.original_bytes)
        if (
            type(self.content) is not bytes
            or len(self.content) > MAX_CANONICAL_FILE_BYTES
            or self.before_sha256 != self.authority.sha256
            or self.after_sha256 != hashlib.sha256(self.content).hexdigest()
            or type(self.changed_edits) is not tuple
            or len(self.changed_edits) > MAX_CANONICAL_VALUES
            or any(type(edit) not in (WriteEdit, WriteInsert) for edit in self.changed_edits)
        ):
            raise WritebackRejected(WritebackReason.INVALID_OUTPUT)
        _attributes(self.attributes)


def apply_byte_edits(
    content: bytes,
    edits: tuple[ByteEdit, ...],
    *,
    max_bytes: int = MAX_CANONICAL_FILE_BYTES,
) -> bytes:
    """Assemble original slices exactly once; validate every edit before allocating output.

    Offsets always address the original content. Overlapping or duplicate positions
    cannot be interpreted as an implicit edit order. The untouched slices are copied
    verbatim, which proves the unchanged-byte complement by construction.
    """
    if (
        type(content) is not bytes
        or not _integer(max_bytes, 0, MAX_CANONICAL_FILE_BYTES)
        or len(content) > max_bytes
        or type(edits) is not tuple
        or len(edits) > MAX_CANONICAL_VALUES
    ):
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    if any(type(edit) is not ByteEdit for edit in edits):
        raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
    if not edits:
        return content
    ordered = sorted(edits, key=lambda edit: (edit.start, edit.end))
    previous_start = -1
    previous_end = 0
    output_size = len(content)
    for edit in ordered:
        if edit.end > len(content) or edit.start < previous_end or edit.start == previous_start:
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        previous_start, previous_end = edit.start, edit.end
        output_size += len(edit.replacement) - (edit.end - edit.start)
    if output_size > max_bytes:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    parts: list[bytes] = []
    cursor = 0
    for edit in ordered:
        parts.extend((content[cursor : edit.start], edit.replacement))
        cursor = edit.end
    parts.append(content[cursor:])
    return b"".join(parts)
