"""Closed confirmed-format dispatch for canonical localization parsing."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

from verboflex.localization.importing.android_xml import parse_android_xml
from verboflex.localization.importing.core import (
    MAX_CANONICAL_AGGREGATE_BYTES,
    MAX_CANONICAL_FILE_BYTES,
    MAX_CANONICAL_FILES,
    MAX_CANONICAL_ISSUES,
    MAX_CANONICAL_VALUES,
    CanonicalFormat,
    CanonicalIssue,
    CanonicalOutputBudget,
    CanonicalOutputLimitExceeded,
    CanonicalParser,
    CanonicalParseResult,
    CanonicalParserInput,
    CanonicalValue,
    CanonicalValueBuffer,
    IssueCode,
    canonical_issue_order,
    canonical_result_is_valid,
    canonical_selector_bytes,
    canonical_value_order,
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
_REPOSITORY_SIDE_ORDER = {"direct": 0, "keys": 1, "translations": 2}


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
    adapter = _ADAPTERS.get(parser_input.format)
    if adapter is None:
        return _failure(parser_input, code="unsupported_structure")
    try:
        result = adapter(parser_input)
    except Exception:
        return _failure(parser_input, code="malformed_file")
    if not canonical_result_is_valid(result) or not _result_matches_input(result, parser_input):
        return _failure(parser_input, code="malformed_file")
    return result


def parse_canonical_mapping(
    parser_inputs: tuple[CanonicalParserInput, ...],
) -> CanonicalParseResult:
    """Parse one complete direct or separate mapping as an atomic result."""
    if type(parser_inputs) is not tuple or not parser_inputs:
        return _invalid_input_failure()
    if any(type(parser_input) is not CanonicalParserInput for parser_input in parser_inputs):
        return _invalid_input_failure()

    ordered_inputs = tuple(
        parser_input
        for _, parser_input in sorted(
            enumerate(parser_inputs),
            key=lambda item: (
                _REPOSITORY_SIDE_ORDER.get(item[1].repository_side, 3),
                item[1].path,
                item[0],
            ),
        )
    )
    first = ordered_inputs[0]
    if any(type(parser_input.content) is not bytes for parser_input in ordered_inputs):
        return _failure(first, code="malformed_file")
    if len(ordered_inputs) > MAX_CANONICAL_FILES:
        return _failure(first, code="unsupported_structure")
    if any(len(parser_input.content) > MAX_CANONICAL_FILE_BYTES for parser_input in ordered_inputs):
        return _failure(first, code="unsupported_structure")
    if sum(len(parser_input.content) for parser_input in ordered_inputs) > (
        MAX_CANONICAL_AGGREGATE_BYTES
    ):
        return _failure(first, code="unsupported_structure")
    if len({parser_input.format for parser_input in ordered_inputs}) != 1:
        return _failure(first, code="ambiguous_structure")

    normalized_bases = tuple(
        normalize_preview_locale(parser_input.base_language) for parser_input in ordered_inputs
    )
    if any(base_language is None for base_language in normalized_bases):
        return _failure(first, code="base_language_required")
    if len(set(normalized_bases)) != 1:
        return _failure(first, code="ambiguous_structure")
    if len(
        {(parser_input.repository_side, parser_input.path) for parser_input in ordered_inputs}
    ) != len(ordered_inputs):
        return _failure(first, code="duplicate_key")

    sides = {parser_input.repository_side for parser_input in ordered_inputs}
    if sides == {"direct"}:
        return _parse_complete_inputs(ordered_inputs)
    if sides != {"keys", "translations"}:
        return _failure(first, code="ambiguous_structure")

    source_bytes = sum(len(item.content) for item in ordered_inputs)
    budget = CanonicalOutputBudget(source_bytes=source_bytes)
    keys_result = _parse_complete_inputs(
        tuple(item for item in ordered_inputs if item.repository_side == "keys"), budget=budget
    )
    translations_result = _parse_complete_inputs(
        tuple(item for item in ordered_inputs if item.repository_side == "translations"),
        budget=budget,
    )
    issues = (*keys_result.issues, *translations_result.issues)
    if issues:
        return CanonicalParseResult(
            issues=tuple(sorted(set(issues), key=canonical_issue_order)[:MAX_CANONICAL_ISSUES])
        )
    return _join_separate_results(
        keys_result=keys_result,
        translations_result=translations_result,
        failure_input=first,
        source_bytes=source_bytes,
    )


def _parse_complete_inputs(
    parser_inputs: tuple[CanonicalParserInput, ...],
    *,
    budget: CanonicalOutputBudget | None = None,
) -> CanonicalParseResult:
    values = CanonicalValueBuffer(
        budget, source_bytes=sum(len(item.content) for item in parser_inputs)
    )
    issues: list[CanonicalIssue] = []
    for parser_input in parser_inputs:
        result = parse_canonical_snapshot(parser_input)
        if result.issues:
            issues.extend(result.issues)
        else:
            try:
                values.extend(result.values)
            except CanonicalOutputLimitExceeded:
                return _failure(parser_input, code="unsupported_structure")
    if issues:
        return CanonicalParseResult(
            issues=tuple(sorted(set(issues), key=canonical_issue_order)[:MAX_CANONICAL_ISSUES])
        )
    if len(values) > MAX_CANONICAL_VALUES:
        return _failure(parser_inputs[0], code="unsupported_structure")
    try:
        return CanonicalParseResult(values=tuple(sorted(values, key=canonical_value_order)))
    except ValueError:
        return _failure(parser_inputs[0], code="duplicate_key")


def _join_separate_results(
    *,
    keys_result: CanonicalParseResult,
    translations_result: CanonicalParseResult,
    failure_input: CanonicalParserInput,
    source_bytes: int = 0,
) -> CanonicalParseResult:
    source_by_identity: dict[tuple[str, bytes], CanonicalValue] = {}
    key_selectors: dict[str, set[bytes]] = {}
    translation_selectors: dict[str, set[bytes]] = {}
    for value in keys_result.values:
        if value.source_text is None or value.translated_text is not None:
            return _failure(failure_input, code="malformed_file")
        identity = (value.logical_key, canonical_selector_bytes(value.selector))
        if identity in source_by_identity:
            return _failure(failure_input, code="duplicate_key")
        source_by_identity[identity] = value
        key_selectors.setdefault(value.logical_key, set()).add(identity[1])

    for value in translations_result.values:
        if value.translated_text is None:
            return _failure(failure_input, code="malformed_file")
        translation_selectors.setdefault(value.logical_key, set()).add(
            canonical_selector_bytes(value.selector)
        )
    for logical_key in key_selectors.keys() & translation_selectors.keys():
        if key_selectors[logical_key] != translation_selectors[logical_key]:
            return _failure(failure_input, code="unsupported_structure")

    joined_translations = (
        replace(
            value,
            source_text=(
                source.source_text
                if (
                    source := source_by_identity.get(
                        (value.logical_key, canonical_selector_bytes(value.selector))
                    )
                )
                else None
            ),
        )
        for value in translations_result.values
    )
    values = CanonicalValueBuffer(source_bytes=source_bytes)
    try:
        values.extend(keys_result.values)
        values.extend(joined_translations)
    except CanonicalOutputLimitExceeded:
        return _failure(failure_input, code="unsupported_structure")
    if len(values) > MAX_CANONICAL_VALUES:
        return _failure(failure_input, code="unsupported_structure")
    try:
        return CanonicalParseResult(values=tuple(sorted(values, key=canonical_value_order)))
    except ValueError:
        return _failure(failure_input, code="duplicate_key")


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
        parser_input.repository_side
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
