"""Closed confirmed-format dispatch for canonical localization parsing."""

from __future__ import annotations

from types import MappingProxyType
from typing import cast

from verboflex.localization.importing.android_xml import parse_android_xml
from verboflex.localization.importing.core import (
    CanonicalFormat,
    CanonicalIssue,
    CanonicalParser,
    CanonicalParseResult,
    CanonicalParserInput,
    IssueCode,
    RepositorySide,
)
from verboflex.localization.preview.core import normalize_preview_locale

_ISSUE_MESSAGES: dict[IssueCode, str] = {
    "malformed_file": "Canonical parser input is invalid.",
    "ambiguous_structure": "Confirmed localization layout is invalid.",
    "unsupported_structure": "Confirmed localization format is unsupported.",
    "duplicate_key": "Duplicate localization key.",
    "base_language_required": "Base language is required.",
}


def _unsupported_adapter(parser_input: CanonicalParserInput) -> CanonicalParseResult:
    return _failure(parser_input, code="unsupported_structure")


_ADAPTERS: MappingProxyType[CanonicalFormat, CanonicalParser] = MappingProxyType(
    {
        "android_xml": parse_android_xml,
        "qt_ts": _unsupported_adapter,
        "json": _unsupported_adapter,
        "ios_strings": _unsupported_adapter,
    }
)


def parse_canonical_snapshot(parser_input: CanonicalParserInput) -> CanonicalParseResult:
    """Validate one immutable confirmed input and dispatch its exact adapter."""
    if type(parser_input) is not CanonicalParserInput:
        return _invalid_input_failure()
    if parser_input.repository_side not in {"direct", "keys", "translations"}:
        return _failure(parser_input, code="malformed_file")
    if not _is_safe_relative_path(parser_input.path) or not isinstance(parser_input.content, bytes):
        return _failure(parser_input, code="malformed_file")
    if not _is_safe_relative_path(parser_input.layout_identity) or parser_input.layout_version != 1:
        return _failure(parser_input, code="ambiguous_structure")
    if normalize_preview_locale(parser_input.base_language) is None:
        return _failure(parser_input, code="base_language_required")
    adapter = _ADAPTERS.get(cast(CanonicalFormat, parser_input.format))
    if adapter is None:
        return _failure(parser_input, code="unsupported_structure")
    result = adapter(parser_input)
    if not isinstance(result, CanonicalParseResult):
        return _failure(parser_input, code="malformed_file")
    return result


def _is_safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or len(value) > 4096 or "\x00" in value:
        return False
    if value.startswith("/") or "//" in value:
        return False
    return all(component not in {"", ".", ".."} for component in value.split("/"))


def _failure(parser_input: CanonicalParserInput, *, code: IssueCode) -> CanonicalParseResult:
    side = (
        cast(RepositorySide, parser_input.repository_side)
        if parser_input.repository_side in {"direct", "keys", "translations"}
        else "direct"
    )
    path = parser_input.path if _is_safe_relative_path(parser_input.path) else "<input>"
    return CanonicalParseResult(
        issues=(
            CanonicalIssue(
                code=code,
                repository_side=side,
                path=path,
                message=_ISSUE_MESSAGES[code],
            ),
        )
    )


def _invalid_input_failure() -> CanonicalParseResult:
    return CanonicalParseResult(
        issues=(
            CanonicalIssue(
                code="malformed_file",
                repository_side="direct",
                path="<input>",
                message=_ISSUE_MESSAGES["malformed_file"],
            ),
        )
    )
