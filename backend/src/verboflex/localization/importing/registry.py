"""Closed confirmed-format dispatch for canonical localization parsing."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import cast

from verboflex.localization.importing.android_xml import (
    AndroidDiagnosticKey,
    inspect_android_xml,
    inspect_unsupported_android_scalar_keys,
    parse_android_xml,
)
from verboflex.localization.importing.core import (
    MAX_CANONICAL_AGGREGATE_BYTES,
    MAX_CANONICAL_FILE_BYTES,
    MAX_CANONICAL_FILES,
    MAX_CANONICAL_ISSUES,
    MAX_CANONICAL_MAPPING_VALUES,
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
from verboflex.localization.importing.ios_strings import inspect_ios_strings, parse_ios_strings
from verboflex.localization.importing.json import inspect_json_localization, parse_json_localization
from verboflex.localization.importing.qt_ts import inspect_qt_ts, parse_qt_ts
from verboflex.localization.importing.xliff import inspect_xliff, parse_xliff
from verboflex.localization.preview.core import normalize_preview_locale
from verboflex.localization.preview.ios_strings import ios_layout_path

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
        "xliff": parse_xliff,
    }
)
_REPOSITORY_SIDE_ORDER = {"direct": 0, "keys": 1, "translations": 2}


def inspect_duplicate_snapshot(
    parser_input: CanonicalParserInput,
) -> tuple[tuple[CanonicalValue | AndroidDiagnosticKey, ...], tuple[CanonicalIssue, ...]]:
    """Diagnostic-only dispatch; no canonical uniqueness rule is relaxed."""
    if parser_input.format == "android_xml":
        inspected = inspect_android_xml(parser_input)
        values = (
            inspect_unsupported_android_scalar_keys(parser_input)
            if inspected.issues
            else inspected.values
        )
        return values, inspected.issues
    inspectors = {
        "json": inspect_json_localization,
        "ios_strings": inspect_ios_strings,
        "qt_ts": inspect_qt_ts,
        "xliff": inspect_xliff,
    }
    inspector = inspectors.get(parser_input.format)
    if inspector is None:
        parsed = parse_canonical_snapshot(parser_input)
        return parsed.values, parsed.issues
    diagnostic = inspector(parser_input)
    return diagnostic.values, diagnostic.issues


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

    effective_inputs = prefer_explicit_ios_base_inputs(ordered_inputs)
    sides = {parser_input.repository_side for parser_input in effective_inputs}
    budget = CanonicalOutputBudget(mapping=True)
    if sides == {"direct"}:
        return _parse_complete_inputs(effective_inputs, budget=budget)
    if sides != {"keys", "translations"}:
        return _failure(first, code="ambiguous_structure")

    formats = {item.format for item in effective_inputs}
    if any(
        {item.repository_side for item in effective_inputs if item.format == format_name} != sides
        for format_name in formats
    ):
        return _failure(first, code="ambiguous_structure")

    source_bytes = sum(len(item.content) for item in ordered_inputs)
    keys_result = _parse_complete_inputs(
        tuple(item for item in effective_inputs if item.repository_side == "keys"), budget=budget
    )
    translations_result = _parse_complete_inputs(
        tuple(item for item in effective_inputs if item.repository_side == "translations"),
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


def prefer_explicit_ios_base_inputs(
    parser_inputs: tuple[CanonicalParserInput, ...],
) -> tuple[CanonicalParserInput, ...]:
    """Drop a Base.lproj fallback only when its explicit base-locale peer exists."""
    explicit_base_layouts: set[tuple[str, str, str]] = set()
    for parser_input in parser_inputs:
        if parser_input.format != "ios_strings":
            continue
        path_layout = ios_layout_path(parser_input.path)
        base_language = normalize_preview_locale(parser_input.base_language)
        if (
            path_layout is not None
            and base_language is not None
            and path_layout[0] == base_language
        ):
            explicit_base_layouts.add(
                (parser_input.repository_side, parser_input.layout_identity, base_language)
            )
    return tuple(
        parser_input
        for parser_input in parser_inputs
        if not _is_shadowed_ios_base_fallback(parser_input, explicit_base_layouts)
    )


def _is_shadowed_ios_base_fallback(
    parser_input: CanonicalParserInput,
    explicit_base_layouts: set[tuple[str, str, str]],
) -> bool:
    if parser_input.format != "ios_strings":
        return False
    path_layout = ios_layout_path(parser_input.path)
    base_language = normalize_preview_locale(parser_input.base_language)
    return (
        path_layout is not None
        and path_layout[0] == "default"
        and base_language is not None
        and (parser_input.repository_side, parser_input.layout_identity, base_language)
        in explicit_base_layouts
    )


def parse_canonical_mapping_quarantining_duplicates(
    parser_inputs: tuple[CanonicalParserInput, ...],
) -> CanonicalParseResult:
    """Parse a mapping while excluding every occurrence of duplicate identities.

    Malformed, ambiguous, incomplete, and unsupported inputs remain fail-closed.
    This boundary never chooses a first or last duplicate occurrence.
    """
    strict = parse_canonical_mapping(parser_inputs)
    if not strict.issues or any(issue.code != "duplicate_key" for issue in strict.issues):
        return strict

    # Local import avoids a module cycle: diagnostics dispatches individual
    # source inspection through this registry.
    from verboflex.localization.duplicate_diagnostics import (
        DuplicateGroup,
        duplicate_identity_digest,
        duplicate_value_identity,
        inspect_duplicate_keys,
    )

    report = inspect_duplicate_keys(parser_inputs)
    if not report.complete or not report.groups:
        return strict
    quarantined: dict[tuple[str, str, int], list[DuplicateGroup]] = {}
    for group in report.groups:
        for occurrence in group.occurrences:
            quarantined.setdefault(
                (group.repository_side, occurrence.path, occurrence.position), []
            ).append(group)
    values_by_side: dict[str, list[CanonicalValue]] = {
        "direct": [],
        "keys": [],
        "translations": [],
    }
    for parser_input in parser_inputs:
        inspected, issues = inspect_duplicate_snapshot(parser_input)
        if issues or any(type(value) is not CanonicalValue for value in inspected):
            return strict
        for raw_value in inspected:
            value = cast(CanonicalValue, raw_value)
            identity = duplicate_value_identity(parser_input, value)
            groups = quarantined.get(
                (parser_input.repository_side, parser_input.path, value.locator.position), ()
            )
            if not any(
                duplicate_identity_digest(identity[0], group.layout_identity, *identity[2:])
                == group.id
                for group in groups
            ):
                values_by_side[parser_input.repository_side].append(value)

    budget = CanonicalOutputBudget(mapping=True)
    sides = {parser_input.repository_side for parser_input in parser_inputs}
    if sides == {"direct"}:
        return _canonical_quarantined_values(
            tuple(values_by_side["direct"]), failure_input=parser_inputs[0], budget=budget
        )
    if sides != {"keys", "translations"}:
        return strict
    keys_result = _canonical_quarantined_values(
        tuple(values_by_side["keys"]), failure_input=parser_inputs[0], budget=budget
    )
    translations_result = _canonical_quarantined_values(
        tuple(values_by_side["translations"]), failure_input=parser_inputs[0], budget=budget
    )
    if keys_result.issues or translations_result.issues:
        return strict
    return _join_separate_results(
        keys_result=keys_result,
        translations_result=translations_result,
        failure_input=parser_inputs[0],
        source_bytes=sum(len(item.content) for item in parser_inputs),
    )


def _canonical_quarantined_values(
    values: tuple[CanonicalValue, ...],
    *,
    failure_input: CanonicalParserInput,
    budget: CanonicalOutputBudget,
) -> CanonicalParseResult:
    retained = CanonicalValueBuffer(budget)
    try:
        retained.extend(values)
        return CanonicalParseResult(values=tuple(sorted(retained, key=canonical_value_order)))
    except CanonicalOutputLimitExceeded:
        return _failure(failure_input, code="unsupported_structure")
    except ValueError:
        return _failure(failure_input, code="duplicate_key")


def _parse_complete_inputs(
    parser_inputs: tuple[CanonicalParserInput, ...],
    *,
    budget: CanonicalOutputBudget | None = None,
) -> CanonicalParseResult:
    values = CanonicalValueBuffer(
        budget if budget is not None else CanonicalOutputBudget(mapping=True)
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
    if len(values) > MAX_CANONICAL_MAPPING_VALUES:
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
    values = CanonicalValueBuffer(CanonicalOutputBudget(mapping=True))
    try:
        values.extend(keys_result.values)
        values.extend(joined_translations)
    except CanonicalOutputLimitExceeded:
        return _failure(failure_input, code="unsupported_structure")
    if len(values) > MAX_CANONICAL_MAPPING_VALUES:
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
