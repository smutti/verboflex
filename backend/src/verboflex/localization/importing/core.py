"""Immutable contracts for complete, fail-closed localization parsing."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Literal, Protocol, TypeGuard, get_args

from verboflex.localization.preview.core import normalize_preview_locale

CanonicalFormat = Literal["android_xml", "qt_ts", "json", "ios_strings", "xliff"]
RepositorySide = Literal["direct", "keys", "translations"]
SelectorKind = Literal[
    "scalar",
    "android_quantity",
    "android_array_item",
    "qt_numerus",
    "qt_length_variant",
    "json_path",
]
ReviewState = Literal["draft", "approved", "rejected"]
IssueCode = Literal[
    "malformed_file",
    "ambiguous_structure",
    "unsupported_structure",
    "duplicate_key",
    "base_language_required",
]
StructureKind = Literal[
    "android_xml:string",
    "android_xml:plurals",
    "android_xml:string_array",
    "android_xml:item",
    "android_xml:text",
    "android_xml:inline",
    "android_xml:tail",
    "android_xml:comment",
    "android_xml:cdata",
    "qt_ts:document",
    "qt_ts:defaultcodec",
    "qt_ts:dependencies",
    "qt_ts:dependency",
    "qt_ts:context",
    "qt_ts:message",
    "qt_ts:location",
    "qt_ts:source",
    "qt_ts:oldsource",
    "qt_ts:comment",
    "qt_ts:oldcomment",
    "qt_ts:extracomment",
    "qt_ts:translatorcomment",
    "qt_ts:userdata",
    "qt_ts:translation",
    "qt_ts:numerusform",
    "qt_ts:lengthvariant",
    "qt_ts:text",
    "json:document",
    "json:object",
    "json:member",
    "json:string",
    "ios_strings:document",
    "ios_strings:encoding",
    "ios_strings:comment",
    "ios_strings:entry",
    "ios_strings:key",
    "ios_strings:value",
    "ios_strings:whitespace",
    "xliff:document",
    "xliff:file",
    "xliff:group",
    "xliff:unit",
    "xliff:segment",
    "xliff:source",
    "xliff:target",
    "xliff:notes",
    "xliff:note",
    "xliff:original_data",
    "xliff:data",
    "xliff:metadata",
    "xliff:inline",
    "xliff:text",
    "xliff:tail",
]
type ScalarField = str | int | bool
type SequenceField = tuple[str, ...] | tuple[int, ...]
type CanonicalFieldValue = ScalarField | SequenceField
type CanonicalFields = tuple[tuple[str, CanonicalFieldValue], ...]

SELECTOR_SCHEMA_VERSION = 1
STRUCTURE_SCHEMA_VERSION = 1
MAX_CANONICAL_FILE_BYTES = 1_048_576
MAX_CANONICAL_AGGREGATE_BYTES = 20_971_520
MAX_CANONICAL_FILES = 500
MAX_CANONICAL_VALUES = 5_000
MAX_CANONICAL_MAPPING_VALUES = 100_000
MAX_CANONICAL_MAPPING_OUTPUT_BYTES = 128 * 1_048_576
MAX_CANONICAL_DEPTH = 12
MAX_CANONICAL_ISSUES = 5
MAX_CANONICAL_PATH_LENGTH = 4096
MAX_CANONICAL_TEXT_LENGTH = 1_048_576
MAX_CANONICAL_FIELD_NAME_LENGTH = 128
MAX_CANONICAL_SEQUENCE_LENGTH = 4096
# iOS permits 4096 comments plus interleaved whitespace and syntax nodes.
# Format-specific limits may be stricter than this complete-value ceiling.
MAX_CANONICAL_STRUCTURE_NODES = 16_384
MAX_CANONICAL_ADDRESS_LENGTH = 128
MAX_CANONICAL_COORDINATE = 2_147_483_647
MAX_CANONICAL_ISSUE_MESSAGE_LENGTH = 256

_CANONICAL_FORMATS = frozenset(get_args(CanonicalFormat))
_REPOSITORY_SIDES = frozenset(get_args(RepositorySide))
_SELECTOR_KINDS = frozenset(get_args(SelectorKind))
_ISSUE_CODES = frozenset(get_args(IssueCode))
_STRUCTURE_KINDS = frozenset(get_args(StructureKind))
_REPOSITORY_SIDE_ORDER = {"direct": 0, "keys": 1, "translations": 2}


@dataclass(frozen=True, slots=True)
class CanonicalParserInput:
    """One immutable repository file under confirmed parser authority."""

    format: CanonicalFormat
    repository_side: RepositorySide
    path: str
    content: bytes
    layout_identity: str
    layout_version: int
    base_language: str


@dataclass(frozen=True, slots=True)
class CanonicalSelector:
    """Versioned typed value discriminator independent of the raw logical key."""

    kind: SelectorKind
    fields: CanonicalFields
    schema_version: int = SELECTOR_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            self.kind not in _SELECTOR_KINDS
            or not _is_exact_int(self.schema_version)
            or self.schema_version != SELECTOR_SCHEMA_VERSION
        ):
            raise ValueError("canonical selector rejected")
        _validate_fields(self.fields, error_message="canonical selector rejected")

    def to_mapping(self) -> dict[str, object]:
        return {
            "fields": {name: _field_to_json(value) for name, value in self.fields},
            "kind": self.kind,
            "version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class CanonicalStructureNode:
    """One ordered, format-qualified semantic node."""

    kind: StructureKind
    fields: CanonicalFields
    schema_version: int = STRUCTURE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            self.kind not in _STRUCTURE_KINDS
            or not _is_exact_int(self.schema_version)
            or self.schema_version != STRUCTURE_SCHEMA_VERSION
        ):
            raise ValueError("canonical structure node rejected")
        _validate_fields(self.fields, error_message="canonical structure node rejected")

    def to_mapping(self) -> dict[str, object]:
        return {
            "fields": [
                {"name": name, "value": _field_to_json(value)} for name, value in self.fields
            ],
            "kind": self.kind,
            "version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class CanonicalLocator:
    """Mutable source location kept outside stable value identity."""

    format: CanonicalFormat
    repository_side: RepositorySide
    path: str
    position: int
    structural_address: tuple[str | int, ...]
    line: int | None = None
    column: int | None = None

    def __post_init__(self) -> None:
        if self.format not in _CANONICAL_FORMATS:
            raise ValueError("canonical locator rejected")
        if self.repository_side not in _REPOSITORY_SIDES:
            raise ValueError("canonical locator rejected")
        if not _is_safe_relative_path(self.path):
            raise ValueError("canonical locator rejected")
        if not _is_bounded_index(self.position):
            raise ValueError("canonical locator rejected")
        if (
            type(self.structural_address) is not tuple
            or not self.structural_address
            or len(self.structural_address) > MAX_CANONICAL_ADDRESS_LENGTH
            or any(not _is_address_part(part) for part in self.structural_address)
        ):
            raise ValueError("canonical locator rejected")
        if not _is_optional_coordinate(self.line) or not _is_optional_coordinate(self.column):
            raise ValueError("canonical locator rejected")

    def to_mapping(self) -> dict[str, object]:
        return {
            "column": self.column,
            "format": self.format,
            "line": self.line,
            "path": self.path,
            "position": self.position,
            "repository_side": self.repository_side,
            "structural_address": list(self.structural_address),
        }


@dataclass(frozen=True, slots=True)
class CanonicalValue:
    """One individually addressable localization value."""

    logical_key: str
    language: str
    selector: CanonicalSelector
    source_text: str | None
    translated_text: str | None
    display_text: str
    structure: tuple[CanonicalStructureNode, ...]
    locator: CanonicalLocator

    def __post_init__(self) -> None:
        if not _is_bounded_text(self.logical_key, allow_empty=False):
            raise ValueError("canonical value rejected")
        if (
            not isinstance(self.language, str)
            or normalize_preview_locale(self.language) != self.language
        ):
            raise ValueError("canonical value rejected")
        if type(self.selector) is not CanonicalSelector:
            raise ValueError("canonical value rejected")
        if not _is_optional_text(self.source_text) or not _is_optional_text(self.translated_text):
            raise ValueError("canonical value rejected")
        if not _is_bounded_text(self.display_text, allow_empty=True):
            raise ValueError("canonical value rejected")
        if (
            type(self.structure) is not tuple
            or not self.structure
            or len(self.structure) > MAX_CANONICAL_STRUCTURE_NODES
            or any(type(node) is not CanonicalStructureNode for node in self.structure)
        ):
            raise ValueError("canonical value rejected")
        if type(self.locator) is not CanonicalLocator:
            raise ValueError("canonical value rejected")
        expected_prefix = f"{self.locator.format}:"
        if any(not node.kind.startswith(expected_prefix) for node in self.structure):
            raise ValueError("canonical value rejected")

    def to_mapping(self) -> dict[str, object]:
        return {
            "display_text": self.display_text,
            "language": self.language,
            "locator": self.locator.to_mapping(),
            "logical_key": self.logical_key,
            "selector": self.selector.to_mapping(),
            "source_text": self.source_text,
            "structure": [node.to_mapping() for node in self.structure],
            "translated_text": self.translated_text,
        }


class CanonicalOutputLimitExceeded(ValueError):
    """Canonical expansion exceeded its bounded source-plus-20-MiB allowance."""


@dataclass(slots=True)
class CanonicalOutputBudget:
    source_bytes: int = 0
    used_bytes: int = 0
    mapping: bool = False
    used_values: int = 0

    @property
    def remaining_bytes(self) -> int:
        if self.mapping:
            return MAX_CANONICAL_MAPPING_OUTPUT_BYTES - self.used_bytes
        return MAX_CANONICAL_AGGREGATE_BYTES + self.source_bytes - self.used_bytes


class CanonicalValueBuffer:
    """Retain only bounded compact UTF-8 JSON value output, incrementally.

    Individual values already have bounded fields and structure. Counting encoder
    chunks avoids allocating a complete serialized document. Nested adapter
    buffers bound intermediates before they can be merged into a whole file.
    """

    def __init__(
        self, budget: CanonicalOutputBudget | None = None, *, source_bytes: int = 0
    ) -> None:
        # The input limit is 20 MiB, so mapping output is at most 40 MiB.
        # Crediting input bytes preserves valid whitespace-rich boundary files;
        # the additional 20 MiB bounds duplicated metadata and JSON overhead.
        self._budget = (
            budget if budget is not None else CanonicalOutputBudget(source_bytes=source_bytes)
        )
        self._values: list[CanonicalValue] = []

    @staticmethod
    def _size(value: CanonicalValue, limit: int) -> int:
        encoder = json.JSONEncoder(ensure_ascii=False, separators=(",", ":"))
        size = 0
        for chunk in encoder.iterencode(value.to_mapping()):
            size += len(chunk.encode("utf-8"))
            if size > limit:
                raise CanonicalOutputLimitExceeded("canonical output limit exceeded")
        return size

    def append(self, value: CanonicalValue) -> None:
        if self._budget.mapping and self._budget.used_values >= MAX_CANONICAL_MAPPING_VALUES:
            raise CanonicalOutputLimitExceeded("canonical value limit exceeded")
        self._budget.used_bytes += self._size(value, self._budget.remaining_bytes)
        self._budget.used_values += 1
        self._values.append(value)

    def extend(self, values: Iterable[CanonicalValue]) -> None:
        for value in values:
            self.append(value)

    def replace_last(self, value: CanonicalValue) -> None:
        old_size = self._size(self._values[-1], self._budget.used_bytes)
        new_size = self._size(value, self._budget.remaining_bytes + old_size)
        self._budget.used_bytes += new_size - old_size
        self._values[-1] = value

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator[CanonicalValue]:
        return iter(self._values)

    def __getitem__(self, index: int) -> CanonicalValue:
        return self._values[index]


@dataclass(frozen=True, slots=True)
class CanonicalIssue:
    """Bounded safe parser failure without source or exception payloads."""

    code: IssueCode
    repository_side: RepositorySide
    path: str
    message: str
    line: int | None = None
    column: int | None = None

    def __post_init__(self) -> None:
        if self.code not in _ISSUE_CODES:
            raise ValueError("canonical issue rejected")
        if self.repository_side not in _REPOSITORY_SIDES:
            raise ValueError("canonical issue rejected")
        if not _is_safe_relative_path(self.path):
            raise ValueError("canonical issue rejected")
        if (
            not isinstance(self.message, str)
            or not self.message
            or len(self.message) > MAX_CANONICAL_ISSUE_MESSAGE_LENGTH
            or any(ord(character) < 32 or ord(character) == 127 for character in self.message)
        ):
            raise ValueError("canonical issue rejected")
        if not _is_optional_coordinate(self.line) or not _is_optional_coordinate(self.column):
            raise ValueError("canonical issue rejected")

    def to_mapping(self) -> dict[str, object]:
        return {
            "code": self.code,
            "column": self.column,
            "line": self.line,
            "message": self.message,
            "path": self.path,
            "repository_side": self.repository_side,
        }


@dataclass(frozen=True, slots=True)
class CanonicalParseResult:
    """A complete canonical result or issues, never both."""

    values: tuple[CanonicalValue, ...] = ()
    issues: tuple[CanonicalIssue, ...] = ()

    def __post_init__(self) -> None:
        if type(self.values) is not tuple or type(self.issues) is not tuple:
            raise ValueError("canonical result rejected")
        if any(type(value) is not CanonicalValue for value in self.values):
            raise ValueError("canonical result rejected")
        if any(type(issue) is not CanonicalIssue for issue in self.issues):
            raise ValueError("canonical result rejected")
        if self.values and self.issues:
            raise ValueError("canonical result rejected")
        if self.values != tuple(sorted(self.values, key=canonical_value_order)):
            raise ValueError("canonical result rejected")
        identities = {
            (
                value.locator.repository_side,
                value.language,
                value.logical_key,
                canonical_selector_digest(value.selector),
            )
            for value in self.values
        }
        if len(identities) != len(self.values):
            raise ValueError("canonical result rejected")
        if self.issues != tuple(sorted(self.issues, key=canonical_issue_order)):
            raise ValueError("canonical result rejected")
        if len(set(self.issues)) != len(self.issues):
            raise ValueError("canonical result rejected")

    def to_mapping(self) -> dict[str, object]:
        return {
            "issues": [issue.to_mapping() for issue in self.issues],
            "values": [value.to_mapping() for value in self.values],
        }


@dataclass(frozen=True, slots=True)
class CanonicalDiagnosticResult:
    """Validated source occurrences for diagnostics, including duplicate identities."""

    values: tuple[CanonicalValue, ...] = ()
    issues: tuple[CanonicalIssue, ...] = ()

    def __post_init__(self) -> None:
        if type(self.values) is not tuple or type(self.issues) is not tuple:
            raise ValueError("canonical diagnostic result rejected")
        if any(type(value) is not CanonicalValue for value in self.values):
            raise ValueError("canonical diagnostic result rejected")
        if any(type(issue) is not CanonicalIssue for issue in self.issues):
            raise ValueError("canonical diagnostic result rejected")
        if self.values and self.issues:
            raise ValueError("canonical diagnostic result rejected")
        if self.values != tuple(sorted(self.values, key=canonical_value_order)):
            raise ValueError("canonical diagnostic result rejected")
        if self.issues != tuple(sorted(self.issues, key=canonical_issue_order)):
            raise ValueError("canonical diagnostic result rejected")
        if len(set(self.issues)) != len(self.issues):
            raise ValueError("canonical diagnostic result rejected")


class CanonicalParser(Protocol):
    """Callable implemented by every confirmed-format parser adapter."""

    def __call__(self, parser_input: CanonicalParserInput) -> CanonicalParseResult: ...


def canonical_selector_bytes(selector: CanonicalSelector) -> bytes:
    """Return deterministic compact JSON bytes for selector identity."""
    return json.dumps(
        selector.to_mapping(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_selector_digest(selector: CanonicalSelector) -> str:
    """Return the stable SHA-256 selector identity digest."""
    return hashlib.sha256(canonical_selector_bytes(selector)).hexdigest()


def canonical_value_order(value: CanonicalValue) -> tuple[int, str, int, str, str, bytes]:
    """Return the single adapter-independent canonical value order."""
    return (
        _REPOSITORY_SIDE_ORDER[value.locator.repository_side],
        value.locator.path,
        value.locator.position,
        value.logical_key,
        value.language,
        canonical_selector_bytes(value.selector),
    )


def canonical_issue_order(issue: CanonicalIssue) -> tuple[int, str, int, int, str, str]:
    """Return the deterministic repository-side and source-location issue order."""
    return (
        _REPOSITORY_SIDE_ORDER[issue.repository_side],
        issue.path,
        issue.line or 0,
        issue.column or 0,
        issue.code,
        issue.message,
    )


def canonical_result_is_valid(
    result: object, *, mapping: bool = False
) -> TypeGuard[CanonicalParseResult]:
    """Validate an adapter result again at the shared trust boundary.

    The canonical dataclasses validate at construction time.  Adapters are still
    treated as untrusted producers here: rebuilding the complete graph catches
    bypassed constructors, mutated frozen instances, and future adapters that
    accidentally return a look-alike payload.
    """
    if type(result) is not CanonicalParseResult:
        return False
    value_limit = MAX_CANONICAL_MAPPING_VALUES if mapping else MAX_CANONICAL_VALUES
    if len(result.values) > value_limit or len(result.issues) > MAX_CANONICAL_ISSUES:
        return False
    try:
        rebuilt_values = tuple(_rebuild_value(value) for value in result.values)
        if mapping:
            counts: dict[tuple[str, str], int] = {}
            used_bytes = 0
            for value in rebuilt_values:
                file_identity = (value.locator.repository_side, value.locator.path)
                counts[file_identity] = counts.get(file_identity, 0) + 1
                if counts[file_identity] > MAX_CANONICAL_VALUES:
                    return False
                used_bytes += CanonicalValueBuffer._size(
                    value, MAX_CANONICAL_MAPPING_OUTPUT_BYTES - used_bytes
                )
        rebuilt_issues = tuple(_rebuild_issue(issue) for issue in result.issues)
        rebuilt = CanonicalParseResult(values=rebuilt_values, issues=rebuilt_issues)
    except AttributeError, TypeError, ValueError:
        return False
    return rebuilt == result


def _rebuild_value(value: object) -> CanonicalValue:
    if type(value) is not CanonicalValue:
        raise ValueError("canonical result rejected")
    selector = CanonicalSelector(
        kind=value.selector.kind,
        fields=value.selector.fields,
        schema_version=value.selector.schema_version,
    )
    structure = tuple(
        CanonicalStructureNode(
            kind=node.kind,
            fields=node.fields,
            schema_version=node.schema_version,
        )
        for node in value.structure
    )
    locator = CanonicalLocator(
        format=value.locator.format,
        repository_side=value.locator.repository_side,
        path=value.locator.path,
        position=value.locator.position,
        structural_address=value.locator.structural_address,
        line=value.locator.line,
        column=value.locator.column,
    )
    return CanonicalValue(
        logical_key=value.logical_key,
        language=value.language,
        selector=selector,
        source_text=value.source_text,
        translated_text=value.translated_text,
        display_text=value.display_text,
        structure=structure,
        locator=locator,
    )


def _rebuild_issue(issue: object) -> CanonicalIssue:
    if type(issue) is not CanonicalIssue:
        raise ValueError("canonical result rejected")
    return CanonicalIssue(
        code=issue.code,
        repository_side=issue.repository_side,
        path=issue.path,
        message=issue.message,
        line=issue.line,
        column=issue.column,
    )


def _field_to_json(value: CanonicalFieldValue) -> object:
    if isinstance(value, tuple):
        return list(value)
    return value


def _validate_fields(fields: object, *, error_message: str) -> None:
    if type(fields) is not tuple:
        raise ValueError(error_message)
    names: set[str] = set()
    for field in fields:
        if type(field) is not tuple or len(field) != 2:
            raise ValueError(error_message)
        name, value = field
        if (
            not isinstance(name, str)
            or not name
            or len(name) > MAX_CANONICAL_FIELD_NAME_LENGTH
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
            or name in names
            or not _is_field_value(value)
        ):
            raise ValueError(error_message)
        names.add(name)


def _is_field_value(value: object) -> bool:
    if isinstance(value, bool):
        return True
    if _is_exact_int(value):
        return -MAX_CANONICAL_COORDINATE <= value <= MAX_CANONICAL_COORDINATE
    if isinstance(value, str):
        return _is_bounded_text(value, allow_empty=True)
    if type(value) is not tuple or len(value) > MAX_CANONICAL_SEQUENCE_LENGTH:
        return False
    if not value:
        return True
    if all(isinstance(item, str) for item in value):
        return all(_is_bounded_text(item, allow_empty=True) for item in value)
    if all(_is_exact_int(item) for item in value):
        return all(-MAX_CANONICAL_COORDINATE <= item <= MAX_CANONICAL_COORDINATE for item in value)
    return False


def _is_exact_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_bounded_index(value: object) -> bool:
    return _is_exact_int(value) and 0 <= value <= MAX_CANONICAL_COORDINATE


def _is_optional_coordinate(value: object) -> bool:
    return value is None or (_is_exact_int(value) and 1 <= value <= MAX_CANONICAL_COORDINATE)


def _is_address_part(value: object) -> bool:
    if _is_bounded_index(value):
        return True
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= MAX_CANONICAL_PATH_LENGTH
        and "\x00" not in value
    )


def _is_safe_relative_path(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_CANONICAL_PATH_LENGTH
        or value.startswith("/")
        or "//" in value
        or "\x00" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return False
    return all(component not in {"", ".", ".."} for component in value.split("/"))


def _is_bounded_text(value: object, *, allow_empty: bool) -> bool:
    return (
        isinstance(value, str)
        and (allow_empty or bool(value))
        and len(value) <= MAX_CANONICAL_TEXT_LENGTH
        and "\x00" not in value
    )


def _is_optional_text(value: object) -> bool:
    return value is None or _is_bounded_text(value, allow_empty=True)
