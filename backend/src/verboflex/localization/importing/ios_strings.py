"""Complete canonical adapter for strict Apple ``.strings`` documents."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, cast
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
from verboflex.localization.preview import ios_strings as preview_ios
from verboflex.localization.preview.core import normalize_preview_locale

type _EncodingName = Literal["utf-8", "utf-16-le", "utf-16-be"]
type _BomName = Literal["none", "utf-8", "utf-16-le", "utf-16-be"]
type _TriviaKind = Literal["whitespace", "line_comment", "block_comment"]
type _TriviaPlacement = Literal[
    "before_entry",
    "after_key",
    "after_equals",
    "after_value",
    "after_document",
]

_UTF8_BOM = b"\xef\xbb\xbf"
_UTF16_LE_BOM = b"\xff\xfe"
_UTF16_BE_BOM = b"\xfe\xff"
_LEXER_WHITESPACE = " \t\r\n"


class _MalformedIosStrings(ValueError):
    def __init__(self, *, position: int | None = None) -> None:
        super().__init__("malformed iOS strings")
        self.position = position


class _UnsupportedIosStrings(ValueError):
    def __init__(self, *, position: int | None = None) -> None:
        super().__init__("unsupported iOS strings")
        self.position = position


class _AmbiguousIosLayout(ValueError):
    pass


class _DuplicateIosKey(ValueError):
    def __init__(self, *, position: int) -> None:
        super().__init__("duplicate iOS strings key")
        self.position = position


class _BaseLanguageRequired(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _DecodedDocument:
    source: str
    encoding: _EncodingName
    bom: _BomName


@dataclass(frozen=True, slots=True)
class _Trivia:
    kind: _TriviaKind
    raw: str
    span: preview_ios.SourceSpan
    placement: _TriviaPlacement


@dataclass(frozen=True, slots=True)
class _LexicalEntry:
    key: str
    value: str
    key_span: preview_ios.SourceSpan
    value_span: preview_ios.SourceSpan
    entry_span: preview_ios.SourceSpan
    equals_span: preview_ios.SourceSpan
    semicolon_span: preview_ios.SourceSpan
    trivia: tuple[_Trivia, ...]


class _CanonicalStringsLexer(preview_ios._StringsLexer):
    """Metadata-retaining extension of the proven preview lexer state machine."""

    __slots__ = ()

    def parse_entries(self) -> tuple[_LexicalEntry, ...]:
        entries: list[_LexicalEntry] = []
        leading = self._trivia(placement="before_entry")
        while self._position < self._length:
            if self._source[self._position] != '"':
                raise _UnsupportedIosStrings(position=self._position)
            entry_start = self._position
            key, key_span = self._quoted()
            if not key:
                raise _UnsupportedIosStrings(position=key_span.start)
            after_key = self._trivia(placement="after_key")
            equals_span = self._punctuation("=")
            after_equals = self._trivia(placement="after_equals")
            if self._position == self._length or self._source[self._position] != '"':
                raise _UnsupportedIosStrings(position=self._position)
            value, value_span = self._quoted()
            after_value = self._trivia(placement="after_value")
            semicolon_span = self._punctuation(";")
            entries.append(
                _LexicalEntry(
                    key=key,
                    value=value,
                    key_span=key_span,
                    value_span=value_span,
                    entry_span=preview_ios.SourceSpan(entry_start, semicolon_span.end),
                    equals_span=equals_span,
                    semicolon_span=semicolon_span,
                    trivia=(*leading, *after_key, *after_equals, *after_value),
                )
            )
            leading = self._trivia(placement="before_entry")

        if not entries:
            raise _MalformedIosStrings(position=self._position)
        if leading:
            trailing = tuple(replace(item, placement="after_document") for item in leading)
            entries[-1] = replace(entries[-1], trivia=(*entries[-1].trivia, *trailing))
        self._require_unique_keys(entries)
        return tuple(entries)

    def _quoted(self) -> tuple[str, preview_ios.SourceSpan]:
        try:
            return self._quoted_string()
        except ValueError as error:
            raise _MalformedIosStrings(position=self._position) from error

    def _punctuation(self, expected: str) -> preview_ios.SourceSpan:
        start = self._position
        try:
            self._expect(expected)
        except ValueError as error:
            raise _MalformedIosStrings(position=start) from error
        return preview_ios.SourceSpan(start, self._position)

    def _trivia(self, *, placement: _TriviaPlacement) -> tuple[_Trivia, ...]:
        trivia: list[_Trivia] = []
        while self._position < self._length:
            start = self._position
            current = self._source[self._position]
            if current in _LEXER_WHITESPACE:
                self._position += 1
                while (
                    self._position < self._length
                    and self._source[self._position] in _LEXER_WHITESPACE
                ):
                    self._position += 1
                kind: _TriviaKind = "whitespace"
            elif self._source.startswith("//", self._position):
                self._position += 2
                while self._position < self._length and self._source[self._position] not in "\r\n":
                    self._position += 1
                kind = "line_comment"
            elif self._source.startswith("/*", self._position):
                self._position += 2
                try:
                    self._consume_block_comment()
                except ValueError as error:
                    raise _MalformedIosStrings(position=self._position) from error
                kind = "block_comment"
            else:
                break
            span = preview_ios.SourceSpan(start, self._position)
            trivia.append(
                _Trivia(
                    kind=kind,
                    raw=self._source[span.start : span.end],
                    span=span,
                    placement=placement,
                )
            )
        return tuple(trivia)

    @staticmethod
    def _require_unique_keys(entries: list[_LexicalEntry]) -> None:
        seen: set[str] = set()
        for entry in entries:
            if entry.key in seen:
                raise _DuplicateIosKey(position=entry.key_span.start)
            seen.add(entry.key)


def parse_ios_strings(parser_input: CanonicalParserInput) -> CanonicalParseResult:
    """Parse one confirmed ``.strings`` file into a complete canonical result."""
    if type(parser_input) is not CanonicalParserInput:
        return _invalid_input_failure()
    decoded: _DecodedDocument | None = None
    try:
        language, base_language = _require_input_authority(parser_input)
        decoded = _decode_document(parser_input.content)
        entries = _CanonicalStringsLexer(decoded.source).parse_entries()
        values = tuple(
            _canonical_value(
                parser_input=parser_input,
                decoded=decoded,
                entry=entry,
                entry_index=entry_index,
                entry_count=len(entries),
                language=language,
                base_language=base_language,
            )
            for entry_index, entry in enumerate(entries)
        )
        return CanonicalParseResult(values=tuple(sorted(values, key=canonical_value_order)))
    except _MalformedIosStrings as error:
        line, column = (
            _safe_coordinates(decoded.source, error.position) if decoded else (None, None)
        )
        return _failure(
            parser_input,
            code="malformed_file",
            line=line,
            column=column,
        )
    except _DuplicateIosKey as error:
        line, column = (
            _safe_coordinates(decoded.source, error.position) if decoded else (None, None)
        )
        return _failure(
            parser_input,
            code="duplicate_key",
            line=line,
            column=column,
        )
    except _AmbiguousIosLayout:
        return _failure(parser_input, code="ambiguous_structure")
    except _BaseLanguageRequired:
        return _failure(parser_input, code="base_language_required")
    except _UnsupportedIosStrings, ValueError:
        return _failure(parser_input, code="unsupported_structure")


def _require_input_authority(parser_input: CanonicalParserInput) -> tuple[str, str]:
    if (
        parser_input.format != "ios_strings"
        or parser_input.repository_side not in {"direct", "keys", "translations"}
        or not isinstance(parser_input.content, bytes)
    ):
        raise _UnsupportedIosStrings
    if parser_input.layout_version != 1:
        raise _AmbiguousIosLayout
    path_layout = preview_ios._ios_layout_path(parser_input.path)
    if path_layout is None or parser_input.layout_identity != path_layout[1]:
        raise _AmbiguousIosLayout
    base_language = normalize_preview_locale(parser_input.base_language)
    if base_language is None:
        raise _BaseLanguageRequired
    return path_layout[0], base_language


def _decode_document(content: bytes) -> _DecodedDocument:
    if content.startswith(_UTF16_LE_BOM):
        encoding: _EncodingName = "utf-16-le"
        bom: _BomName = "utf-16-le"
    elif content.startswith(_UTF16_BE_BOM):
        encoding = "utf-16-be"
        bom = "utf-16-be"
    else:
        encoding = "utf-8"
        bom = "utf-8" if content.startswith(_UTF8_BOM) else "none"
    try:
        source = preview_ios._decode_ios_strings(content)
    except ValueError as error:
        raise _MalformedIosStrings from error
    if any(
        category(character) == "Cc" and character not in {"\t", "\n", "\r"} for character in source
    ):
        raise _MalformedIosStrings
    return _DecodedDocument(source=source, encoding=encoding, bom=bom)


def _canonical_value(
    *,
    parser_input: CanonicalParserInput,
    decoded: _DecodedDocument,
    entry: _LexicalEntry,
    entry_index: int,
    entry_count: int,
    language: str,
    base_language: str,
) -> CanonicalValue:
    source_text, translated_text = _side_texts(
        repository_side=parser_input.repository_side,
        language=language,
        base_language=base_language,
        text=entry.value,
    )
    line, column = _safe_coordinates(decoded.source, entry.entry_span.start)
    return CanonicalValue(
        logical_key=entry.key,
        language=language,
        selector=CanonicalSelector(kind="scalar", fields=()),
        source_text=source_text,
        translated_text=translated_text,
        display_text=entry.value,
        structure=_entry_structure(
            decoded=decoded,
            entry=entry,
            entry_index=entry_index,
            entry_count=entry_count,
        ),
        locator=CanonicalLocator(
            format="ios_strings",
            repository_side=parser_input.repository_side,
            path=parser_input.path,
            position=entry_index,
            structural_address=("document", "entry", entry_index),
            line=line,
            column=column,
        ),
    )


def _entry_structure(
    *,
    decoded: _DecodedDocument,
    entry: _LexicalEntry,
    entry_index: int,
    entry_count: int,
) -> tuple[CanonicalStructureNode, ...]:
    by_placement = {
        placement: tuple(item for item in entry.trivia if item.placement == placement)
        for placement in (
            "before_entry",
            "after_key",
            "after_equals",
            "after_value",
            "after_document",
        )
    }
    return (
        CanonicalStructureNode(
            kind="ios_strings:document",
            fields=(
                ("entry_count", entry_count),
                ("decoded_characters", len(decoded.source)),
            ),
        ),
        CanonicalStructureNode(
            kind="ios_strings:encoding",
            fields=(("encoding", decoded.encoding), ("bom", decoded.bom)),
        ),
        *_trivia_nodes(by_placement["before_entry"]),
        CanonicalStructureNode(
            kind="ios_strings:entry",
            fields=(
                ("index", entry_index),
                ("span_start", entry.entry_span.start),
                ("span_end", entry.entry_span.end),
                ("equals_start", entry.equals_span.start),
                ("equals_end", entry.equals_span.end),
                ("semicolon_start", entry.semicolon_span.start),
                ("semicolon_end", entry.semicolon_span.end),
            ),
        ),
        _quoted_node(kind="ios_strings:key", source=decoded.source, span=entry.key_span),
        *_trivia_nodes(by_placement["after_key"]),
        *_trivia_nodes(by_placement["after_equals"]),
        _quoted_node(kind="ios_strings:value", source=decoded.source, span=entry.value_span),
        *_trivia_nodes(by_placement["after_value"]),
        *_trivia_nodes(by_placement["after_document"]),
    )


def _quoted_node(
    *,
    kind: Literal["ios_strings:key", "ios_strings:value"],
    source: str,
    span: preview_ios.SourceSpan,
) -> CanonicalStructureNode:
    raw = source[span.start : span.end]
    escapes = _escape_sequences(raw)
    return CanonicalStructureNode(
        kind=kind,
        fields=(
            ("raw", raw),
            ("span_start", span.start),
            ("span_end", span.end),
            ("quote_style", "double"),
            ("escape_style", "backslash" if escapes else "literal"),
            ("escapes", escapes),
        ),
    )


def _escape_sequences(raw: str) -> tuple[str, ...]:
    escapes: list[str] = []
    position = 1
    while position < len(raw) - 1:
        if raw[position] != "\\":
            position += 1
            continue
        length = 6 if raw.startswith("\\U", position) else 2
        escapes.append(raw[position : position + length])
        position += length
    return tuple(escapes)


def _trivia_nodes(items: tuple[_Trivia, ...]) -> tuple[CanonicalStructureNode, ...]:
    nodes: list[CanonicalStructureNode] = []
    for item in items:
        fields = (
            ("raw", item.raw),
            ("span_start", item.span.start),
            ("span_end", item.span.end),
            ("placement", item.placement),
        )
        if item.kind == "whitespace":
            nodes.append(CanonicalStructureNode(kind="ios_strings:whitespace", fields=fields))
        else:
            nodes.append(
                CanonicalStructureNode(
                    kind="ios_strings:comment",
                    fields=(
                        ("style", "line" if item.kind == "line_comment" else "block"),
                        *fields,
                    ),
                )
            )
    return tuple(nodes)


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


def _safe_coordinates(source: str, position: int | None) -> tuple[int | None, int | None]:
    if position is None or position < 0 or position > len(source):
        return None, None
    prefix = source[:position]
    line = prefix.count("\n") + prefix.count("\r") - prefix.count("\r\n") + 1
    last_break = max(prefix.rfind("\n"), prefix.rfind("\r"))
    column = position - last_break
    return line, column


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


def _failure(
    parser_input: CanonicalParserInput,
    *,
    code: IssueCode,
    line: int | None = None,
    column: int | None = None,
) -> CanonicalParseResult:
    messages = {
        "malformed_file": "Malformed iOS strings file.",
        "ambiguous_structure": "Ambiguous iOS strings layout.",
        "unsupported_structure": "Unsupported iOS strings structure.",
        "duplicate_key": "Duplicate iOS strings key.",
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
                line=line,
                column=column,
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
                message="Malformed iOS strings parser input.",
            ),
        )
    )
