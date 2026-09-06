"""Strict canonical parser for flat and locale-rooted JSON localization files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unicodedata import category

from verboflex.localization.importing.core import (
    CanonicalDiagnosticResult,
    CanonicalIssue,
    CanonicalLocator,
    CanonicalOutputLimitExceeded,
    CanonicalParseResult,
    CanonicalParserInput,
    CanonicalSelector,
    CanonicalStructureNode,
    CanonicalValue,
    CanonicalValueBuffer,
    IssueCode,
    canonical_issue_order,
    canonical_value_order,
)
from verboflex.localization.preview.core import (
    extract_preview_locale_path,
    normalize_preview_locale,
)

MAX_CANONICAL_FILE_BYTES = 1_048_576
MAX_JSON_AGGREGATE_BYTES = 20_971_520
MAX_JSON_FILES = 500
MAX_JSON_MEMBERS = 5_000
MAX_JSON_VALUES = 5_000
MAX_JSON_DEPTH = 12
MAX_JSON_ISSUES = 5


class _MalformedJson(ValueError):
    pass


class _UnsupportedJson(ValueError):
    pass


class _AmbiguousJsonLayout(ValueError):
    pass


class _DuplicateJsonMember(ValueError):
    pass


class _BaseLanguageRequired(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _JsonObject:
    pairs: tuple[tuple[str, object], ...]


def parse_json_localization(parser_input: CanonicalParserInput) -> CanonicalParseResult:
    """Parse one confirmed JSON localization document without partial output."""
    result = _parse_json_localization(parser_input, allow_duplicates=False)
    if type(result) is not CanonicalParseResult:
        raise AssertionError("canonical JSON parse returned diagnostic output")
    return result


def inspect_json_localization(
    parser_input: CanonicalParserInput,
) -> CanonicalDiagnosticResult | CanonicalParseResult:
    """Parse valid JSON while retaining duplicate members for diagnostics only."""
    return _parse_json_localization(parser_input, allow_duplicates=True)


def _parse_json_localization(
    parser_input: CanonicalParserInput, *, allow_duplicates: bool
) -> CanonicalDiagnosticResult | CanonicalParseResult:
    if type(parser_input) is not CanonicalParserInput:
        return _invalid_input_failure()
    try:
        base_language = _require_input_authority(parser_input)
        root = _load_document(parser_input.content, allow_duplicates=allow_duplicates)
        values = _document_values(
            root=root,
            parser_input=parser_input,
            base_language=base_language,
        )
        sorted_values = tuple(sorted(values, key=canonical_value_order))
        if allow_duplicates:
            return CanonicalDiagnosticResult(values=sorted_values)
        return CanonicalParseResult(values=sorted_values)
    except _MalformedJson:
        return _failure(parser_input, code="malformed_file")
    except _DuplicateJsonMember:
        return _failure(parser_input, code="duplicate_key")
    except _AmbiguousJsonLayout:
        return _failure(parser_input, code="ambiguous_structure")
    except _BaseLanguageRequired:
        return _failure(parser_input, code="base_language_required")
    except _UnsupportedJson, ValueError:
        return _failure(parser_input, code="unsupported_structure")


def parse_json_localization_files(
    parser_inputs: tuple[CanonicalParserInput, ...],
) -> CanonicalParseResult:
    """Combine bounded JSON peer files only when every file parses successfully."""
    if type(parser_inputs) is not tuple or not parser_inputs:
        return _invalid_batch_failure()
    if any(type(item) is not CanonicalParserInput for item in parser_inputs):
        return _invalid_batch_failure()
    if any(not isinstance(item.content, bytes) for item in parser_inputs):
        return _invalid_batch_failure()
    if len(parser_inputs) > MAX_JSON_FILES:
        return _failure(parser_inputs[0], code="unsupported_structure")
    if sum(len(item.content) for item in parser_inputs) > MAX_JSON_AGGREGATE_BYTES:
        return _failure(parser_inputs[0], code="unsupported_structure")

    values = CanonicalValueBuffer(source_bytes=sum(len(item.content) for item in parser_inputs))
    issues: list[CanonicalIssue] = []
    ordered_inputs = sorted(parser_inputs, key=lambda item: (item.repository_side, item.path))
    for parser_input in ordered_inputs:
        result = parse_json_localization(parser_input)
        if result.issues:
            issues.extend(result.issues)
        else:
            try:
                values.extend(result.values)
            except CanonicalOutputLimitExceeded:
                return _failure(parser_input, code="unsupported_structure")
        if len(values) > MAX_JSON_VALUES:
            return _failure(parser_input, code="unsupported_structure")
    if issues:
        return CanonicalParseResult(
            issues=tuple(sorted(set(issues), key=canonical_issue_order)[:MAX_JSON_ISSUES])
        )
    try:
        return CanonicalParseResult(values=tuple(sorted(values, key=canonical_value_order)))
    except ValueError:
        return _failure(ordered_inputs[0], code="duplicate_key")


def _require_input_authority(parser_input: CanonicalParserInput) -> str:
    if (
        parser_input.format != "json"
        or parser_input.repository_side not in {"direct", "keys", "translations"}
        or not _is_safe_relative_path(parser_input.path)
        or not isinstance(parser_input.content, bytes)
    ):
        raise _UnsupportedJson
    if (
        parser_input.layout_version != 1
        or not isinstance(parser_input.layout_identity, str)
        or not parser_input.layout_identity
        or len(parser_input.layout_identity) > 4_096
        or "\x00" in parser_input.layout_identity
    ):
        raise _AmbiguousJsonLayout
    base_language = normalize_preview_locale(parser_input.base_language)
    if base_language is None:
        raise _BaseLanguageRequired
    return base_language


def _load_document(content: bytes, *, allow_duplicates: bool = False) -> _JsonObject:
    if (
        not content
        or len(content) > MAX_CANONICAL_FILE_BYTES
        or content.startswith(b"\xef\xbb\xbf")
        or b"\x00" in content
    ):
        raise _MalformedJson
    try:
        decoded = content.decode("utf-8", errors="strict")
        value = json.loads(
            decoded,
            object_pairs_hook=_retain_object if allow_duplicates else _unique_object,
            parse_constant=_reject_constant,
        )
    except RecursionError as error:
        raise _UnsupportedJson from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _MalformedJson from error
    if type(value) is not _JsonObject:
        raise _UnsupportedJson
    _require_tree_bounds(value)
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> _JsonObject:
    seen: set[str] = set()
    ordered: list[tuple[str, object]] = []
    for key, value in pairs:
        if key in seen:
            raise _DuplicateJsonMember
        seen.add(key)
        ordered.append((key, value))
    return _JsonObject(tuple(ordered))


def _retain_object(pairs: list[tuple[str, object]]) -> _JsonObject:
    return _JsonObject(tuple(pairs))


def _reject_constant(token: str) -> object:
    del token
    raise _UnsupportedJson


def _require_tree_bounds(root: _JsonObject) -> None:
    member_count = 0
    value_count = 0
    stack: list[tuple[_JsonObject, int]] = [(root, 1)]
    while stack:
        value, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise _UnsupportedJson
        member_count += len(value.pairs)
        if member_count > MAX_JSON_MEMBERS:
            raise _UnsupportedJson
        for _, member_value in value.pairs:
            if type(member_value) is _JsonObject:
                stack.append((member_value, depth + 1))
            elif isinstance(member_value, str):
                value_count += 1
                if value_count > MAX_JSON_VALUES:
                    raise _UnsupportedJson


def _document_values(
    *,
    root: _JsonObject,
    parser_input: CanonicalParserInput,
    base_language: str,
) -> tuple[CanonicalValue, ...]:
    flat_identity = _flat_layout_identity(parser_input.path)
    rooted_identity = f"json:locale-rooted:{parser_input.path}"
    values = CanonicalValueBuffer(source_bytes=len(parser_input.content))
    if parser_input.layout_identity == flat_identity:
        path_layout = extract_preview_locale_path(parser_input.path, suffix=".json")
        if path_layout is None:
            raise _AmbiguousJsonLayout
        language = path_layout[0]
        _walk_object(
            value=root,
            parser_input=parser_input,
            base_language=base_language,
            language=language,
            raw_locale=None,
            layout="flat_per_locale",
            parents=(),
            address=(),
            values=values,
        )
    elif parser_input.layout_identity == rooted_identity:
        seen_languages: set[str] = set()
        for locale_index, (raw_locale, locale_value) in enumerate(root.pairs):
            language = _validated_language(raw_locale)
            if language in seen_languages:
                raise _AmbiguousJsonLayout
            seen_languages.add(language)
            if type(locale_value) is not _JsonObject:
                raise _AmbiguousJsonLayout
            _walk_object(
                value=locale_value,
                parser_input=parser_input,
                base_language=base_language,
                language=language,
                raw_locale=raw_locale,
                layout="locale_rooted",
                parents=(),
                address=(raw_locale, locale_index),
                values=values,
            )
    else:
        raise _AmbiguousJsonLayout
    return tuple(values)


def _flat_layout_identity(path: str) -> str | None:
    path_layout = extract_preview_locale_path(path, suffix=".json")
    if path_layout is None:
        return None
    return f"json:flat-per-locale:{path_layout[1]}"


def _validated_language(raw_locale: str) -> str:
    _require_safe_string(raw_locale, allow_empty=False)
    language = normalize_preview_locale(raw_locale)
    if language is None:
        raise _AmbiguousJsonLayout
    return language


def _walk_object(
    *,
    value: _JsonObject,
    parser_input: CanonicalParserInput,
    base_language: str,
    language: str,
    raw_locale: str | None,
    layout: str,
    parents: tuple[str, ...],
    address: tuple[str | int, ...],
    values: CanonicalValueBuffer,
) -> None:
    for member_index, (member_name, member_value) in enumerate(value.pairs):
        _require_safe_string(member_name, allow_empty=False)
        member_address = (*address, member_name, member_index)
        if type(member_value) is _JsonObject:
            _walk_object(
                value=member_value,
                parser_input=parser_input,
                base_language=base_language,
                language=language,
                raw_locale=raw_locale,
                layout=layout,
                parents=(*parents, member_name),
                address=member_address,
                values=values,
            )
            continue
        if not isinstance(member_value, str):
            raise _UnsupportedJson
        _require_safe_string(member_value, allow_empty=True)
        source_text, translated_text = _side_texts(
            repository_side=parser_input.repository_side,
            language=language,
            base_language=base_language,
            text=member_value,
        )
        document_fields: tuple[tuple[str, str], ...]
        if raw_locale is None:
            document_fields = (("layout", layout),)
        else:
            document_fields = (("layout", layout), ("raw_locale", raw_locale))
        values.append(
            CanonicalValue(
                logical_key=member_name,
                language=language,
                selector=CanonicalSelector(
                    kind="json_path",
                    fields=(("parents", parents),),
                ),
                source_text=source_text,
                translated_text=translated_text,
                display_text=member_value,
                structure=(
                    CanonicalStructureNode(kind="json:document", fields=document_fields),
                    CanonicalStructureNode(
                        kind="json:object",
                        fields=(("parents", parents),),
                    ),
                    CanonicalStructureNode(
                        kind="json:member",
                        fields=(("name", member_name), ("index", member_index)),
                    ),
                    CanonicalStructureNode(
                        kind="json:string",
                        fields=(("value", member_value),),
                    ),
                ),
                locator=CanonicalLocator(
                    format="json",
                    repository_side=parser_input.repository_side,
                    path=parser_input.path,
                    position=len(values),
                    structural_address=("document", *member_address),
                ),
            )
        )


def _side_texts(
    *,
    repository_side: str,
    language: str,
    base_language: str,
    text: str,
) -> tuple[str | None, str | None]:
    if repository_side == "keys" or (repository_side == "direct" and language == base_language):
        return text, None
    return None, text


def _require_safe_string(value: str, *, allow_empty: bool) -> None:
    if not allow_empty and not value:
        raise _UnsupportedJson
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value) or any(
        category(character) == "Cc" and character not in {"\t", "\n", "\r"} for character in value
    ):
        raise _MalformedJson


def _is_safe_relative_path(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 4_096
        or value.startswith("/")
        or "//" in value
        or "\x00" in value
    ):
        return False
    return all(component not in {"", ".", ".."} for component in value.split("/"))


def _failure(parser_input: CanonicalParserInput, *, code: IssueCode) -> CanonicalParseResult:
    messages = {
        "malformed_file": "Malformed JSON localization file.",
        "ambiguous_structure": "Ambiguous JSON localization structure.",
        "unsupported_structure": "Unsupported JSON localization structure.",
        "duplicate_key": "Duplicate JSON localization member.",
        "base_language_required": "Base language is required.",
    }
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
                message=messages[code],
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
                message="Malformed JSON parser input.",
            ),
        )
    )


def _invalid_batch_failure() -> CanonicalParseResult:
    return CanonicalParseResult(
        issues=(
            CanonicalIssue(
                code="malformed_file",
                repository_side="direct",
                path="<input>",
                message="Malformed JSON parser input batch.",
            ),
        )
    )
