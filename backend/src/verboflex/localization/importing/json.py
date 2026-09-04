"""Strict canonical parser for flat and locale-rooted JSON localization files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast
from unicodedata import category

from verboflex.localization.importing.core import (
    CanonicalIssue,
    CanonicalLocator,
    CanonicalParseResult,
    CanonicalParserInput,
    CanonicalSelector,
    CanonicalStructureNode,
    CanonicalValue,
    IssueCode,
    RepositorySide,
    canonical_value_order,
)
from verboflex.localization.preview.core import (
    extract_preview_locale_path,
    normalize_preview_locale,
)


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
    if type(parser_input) is not CanonicalParserInput:
        return _invalid_input_failure()
    try:
        base_language = _require_input_authority(parser_input)
        root = _load_document(parser_input.content)
        values = _document_values(
            root=root,
            parser_input=parser_input,
            base_language=base_language,
        )
        return CanonicalParseResult(values=tuple(sorted(values, key=canonical_value_order)))
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


def _load_document(content: bytes) -> _JsonObject:
    if not content or content.startswith(b"\xef\xbb\xbf") or b"\x00" in content:
        raise _MalformedJson
    try:
        decoded = content.decode("utf-8", errors="strict")
        value = json.loads(
            decoded,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _MalformedJson from error
    if type(value) is not _JsonObject:
        raise _UnsupportedJson
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


def _reject_constant(token: str) -> object:
    del token
    raise _UnsupportedJson


def _document_values(
    *,
    root: _JsonObject,
    parser_input: CanonicalParserInput,
    base_language: str,
) -> tuple[CanonicalValue, ...]:
    flat_identity = _flat_layout_identity(parser_input.path)
    rooted_identity = f"json:locale-rooted:{parser_input.path}"
    values: list[CanonicalValue] = []
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
    values: list[CanonicalValue],
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
    if (
        (not allow_empty and not value)
        or any(0xD800 <= ord(character) <= 0xDFFF for character in value)
        or any(
            category(character) == "Cc" and character not in {"\t", "\n", "\r"}
            for character in value
        )
    ):
        raise _UnsupportedJson


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
