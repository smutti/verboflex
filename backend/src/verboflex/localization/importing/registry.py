"""Closed confirmed-format dispatch for canonical localization parsing."""

from __future__ import annotations

from types import MappingProxyType
from typing import cast

from verboflex.localization.importing.android_xml import parse_android_xml
from verboflex.localization.importing.core import (
    MAX_CANONICAL_FILE_BYTES,
    CanonicalFormat,
    CanonicalIssue,
    CanonicalParser,
    CanonicalParseResult,
    CanonicalParserInput,
    IssueCode,
    RepositorySide,
    canonical_result_is_valid,
)
from verboflex.localization.importing.ios_strings import parse_ios_strings
from verboflex.localization.importing.json import parse_json_localization
from verboflex.localization.importing.qt_ts import parse_qt_ts
from verboflex.localization.preview.core import normalize_preview_locale

_ISSUE_MESSAGES: dict[IssueCode, str] = {
    "malformed_file": "Canonical parser input is invalid.",
    "ambiguous_structure": "Confirmed localization layout is invalid.",
    "unsupported_structure": "Confirmed localization format is unsupported.",
    "duplicate_key": "Duplicate localization key.",
    "base_language_required": "Base language is required.",
}


_ADAPTERS: MappingProxyType[CanonicalFormat, CanonicalParser] = MappingProxyType(
    {
        "android_xml": parse_android_xml,
        "qt_ts": parse_qt_ts,
        "json": parse_json_localization,
        "ios_strings": parse_ios_strings,
    }
)


def parse_canonical_snapshot(parser_input: CanonicalParserInput) -> CanonicalParseResult:
    """Validate one immutable confirmed input and dispatch its exact adapter."""
    if type(parser_input) is not CanonicalParserInput:
        return _invalid_input_failure()
    if parser_input.repository_side not in {"direct", "keys", "translations"}:
        return _failure(parser_input, code="malformed_file")
    if (
        not _is_safe_relative_path(parser_input.path)
        or type(parser_input.content) is not bytes
        or len(parser_input.content) > MAX_CANONICAL_FILE_BYTES
    ):
        return _failure(parser_input, code="malformed_file")
    if not _is_safe_relative_path(parser_input.layout_identity) or parser_input.layout_version != 1:
        return _failure(parser_input, code="ambiguous_structure")
    if normalize_preview_locale(parser_input.base_language) is None:
        return _failure(parser_input, code="base_language_required")
    adapter = _ADAPTERS.get(cast(CanonicalFormat, parser_input.format))
    if adapter is None:
        return _failure(parser_input, code="unsupported_structure")
    try:
        result = adapter(parser_input)
    except Exception:
        return _failure(parser_input, code="malformed_file")
    if not canonical_result_is_valid(result) or not _result_matches_input(result, parser_input):
        return _failure(parser_input, code="malformed_file")
    return result


def _result_matches_input(
    result: CanonicalParseResult,
    parser_input: CanonicalParserInput,
) -> bool:
    return all(
        value.locator.format == parser_input.format
        and value.locator.repository_side == parser_input.repository_side
        and value.locator.path == parser_input.path
        for value in result.values
    ) and all(
        issue.repository_side == parser_input.repository_side and issue.path == parser_input.path
        for issue in result.issues
    )


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
