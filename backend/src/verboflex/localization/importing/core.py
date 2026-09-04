"""Immutable contracts for complete, fail-closed localization parsing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Protocol

CanonicalFormat = Literal["android_xml", "qt_ts", "json", "ios_strings"]
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
type ScalarField = str | int | bool
type SequenceField = tuple[str, ...] | tuple[int, ...]
type CanonicalFieldValue = ScalarField | SequenceField
type CanonicalFields = tuple[tuple[str, CanonicalFieldValue], ...]

SELECTOR_SCHEMA_VERSION = 1
STRUCTURE_SCHEMA_VERSION = 1


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

    def to_mapping(self) -> dict[str, object]:
        return {
            "fields": {name: _field_to_json(value) for name, value in self.fields},
            "kind": self.kind,
            "version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class CanonicalStructureNode:
    """One ordered, format-qualified semantic node."""

    kind: str
    fields: CanonicalFields
    schema_version: int = STRUCTURE_SCHEMA_VERSION

    def to_mapping(self) -> dict[str, object]:
        return {
            "fields": {name: _field_to_json(value) for name, value in self.fields},
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


@dataclass(frozen=True, slots=True)
class CanonicalIssue:
    """Bounded safe parser failure without source or exception payloads."""

    code: IssueCode
    repository_side: RepositorySide
    path: str
    message: str
    line: int | None = None
    column: int | None = None

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
        if self.values and self.issues:
            raise ValueError("canonical parse result cannot be partial")

    def to_mapping(self) -> dict[str, object]:
        return {
            "issues": [issue.to_mapping() for issue in self.issues],
            "values": [value.to_mapping() for value in self.values],
        }


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


def canonical_value_order(value: CanonicalValue) -> tuple[str, str, str, str, str, int]:
    """Return the single adapter-independent canonical value order."""
    return (
        value.locator.repository_side,
        value.language,
        value.logical_key,
        canonical_selector_digest(value.selector),
        value.locator.path,
        value.locator.position,
    )


def _field_to_json(value: CanonicalFieldValue) -> object:
    if isinstance(value, tuple):
        return list(value)
    return value
