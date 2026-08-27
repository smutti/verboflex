"""Strict, bounded, read-only iOS strings preview detection."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from verboflex.localization.preview.core import (
    PreviewDetectionResult,
    PreviewLayoutCandidate,
    RepositorySide,
    build_layout_candidate,
    normalize_preview_locale,
)
from verboflex.services.repository_discovery import (
    SOURCE_DISCOVERY_BUDGET,
    RepositorySourceFile,
)

_UTF8_BOM = b"\xef\xbb\xbf"
_UTF16_LE_BOM = b"\xff\xfe"
_UTF16_BE_BOM = b"\xfe\xff"
_UTF32_BOMS = (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")
_ASCII_WHITESPACE = " \t\r\n\f"
_SIMPLE_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Half-open character offsets in the strictly decoded source document."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class IosStringsEntry:
    """One decoded key/value pair with immutable source locations."""

    key: str
    value: str
    key_span: SourceSpan
    value_span: SourceSpan
    entry_span: SourceSpan


@dataclass(frozen=True, slots=True)
class _IosFile:
    path: str
    layout_identity: str
    language: str
    values: dict[str, str]


def _decode_ios_strings(content: bytes) -> str:
    if content.startswith(_UTF32_BOMS):
        raise ValueError("unsupported iOS strings encoding")
    if content.startswith(_UTF16_LE_BOM):
        raw = content[len(_UTF16_LE_BOM) :]
        encoding = "utf-16-le"
    elif content.startswith(_UTF16_BE_BOM):
        raw = content[len(_UTF16_BE_BOM) :]
        encoding = "utf-16-be"
    else:
        raw = content[len(_UTF8_BOM) :] if content.startswith(_UTF8_BOM) else content
        encoding = "utf-8"
    if not raw:
        raise ValueError("unsupported iOS strings encoding")
    try:
        text = raw.decode(encoding, errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("unsupported iOS strings encoding") from error
    if not text or "\x00" in text:
        raise ValueError("unsupported iOS strings encoding")
    return text


class _StringsLexer:
    """Single-pass lexer/parser for the deliberately minimal strings grammar."""

    __slots__ = ("_length", "_position", "_source")

    def __init__(self, source: str) -> None:
        self._source = source
        self._length = len(source)
        self._position = 0

    def parse(self) -> tuple[IosStringsEntry, ...]:
        entries: list[IosStringsEntry] = []
        keys: set[str] = set()
        while True:
            self._skip_trivia()
            if self._position == self._length:
                if not entries:
                    raise ValueError("empty iOS strings document")
                return tuple(entries)
            entry_start = self._position
            key, key_span = self._quoted_string()
            if not key or key in keys:
                raise ValueError("duplicate or empty iOS strings key")
            self._skip_trivia()
            self._expect("=")
            self._skip_trivia()
            value, value_span = self._quoted_string()
            self._skip_trivia()
            self._expect(";")
            keys.add(key)
            entries.append(
                IosStringsEntry(
                    key=key,
                    value=value,
                    key_span=key_span,
                    value_span=value_span,
                    entry_span=SourceSpan(entry_start, self._position),
                )
            )

    def _skip_trivia(self) -> None:
        while self._position < self._length:
            current = self._source[self._position]
            if current in _ASCII_WHITESPACE:
                self._position += 1
                continue
            if not self._source.startswith("/", self._position):
                return
            if self._source.startswith("//", self._position):
                self._position += 2
                while self._position < self._length and self._source[self._position] not in "\r\n":
                    self._position += 1
                continue
            if self._source.startswith("/*", self._position):
                self._position += 2
                self._consume_block_comment()
                continue
            return

    def _consume_block_comment(self) -> None:
        while self._position < self._length:
            if self._source.startswith("*/", self._position):
                self._position += 2
                return
            self._position += 1
        raise ValueError("unterminated iOS strings comment")

    def _quoted_string(self) -> tuple[str, SourceSpan]:
        start = self._position
        self._expect('"')
        decoded: list[str] = []
        while self._position < self._length:
            current = self._source[self._position]
            self._position += 1
            if current == '"':
                return "".join(decoded), SourceSpan(start, self._position)
            if current == "\\":
                decoded.append(self._escape())
                continue
            if ord(current) < 0x20:
                raise ValueError("unsupported control character in iOS strings value")
            decoded.append(current)
        raise ValueError("unterminated iOS strings value")

    def _escape(self) -> str:
        if self._position == self._length:
            raise ValueError("unterminated iOS strings escape")
        escaped = self._source[self._position]
        self._position += 1
        simple = _SIMPLE_ESCAPES.get(escaped)
        if simple is not None:
            return simple
        if escaped != "U":
            raise ValueError("unsupported iOS strings escape")
        code_unit = self._unicode_code_unit()
        if 0xDC00 <= code_unit <= 0xDFFF:
            raise ValueError("isolated iOS strings low surrogate")
        if not 0xD800 <= code_unit <= 0xDBFF:
            return chr(code_unit)
        if not self._source.startswith("\\U", self._position):
            raise ValueError("isolated iOS strings high surrogate")
        self._position += 2
        low_surrogate = self._unicode_code_unit()
        if not 0xDC00 <= low_surrogate <= 0xDFFF:
            raise ValueError("invalid iOS strings surrogate pair")
        scalar = 0x10000 + ((code_unit - 0xD800) << 10) + (low_surrogate - 0xDC00)
        return chr(scalar)

    def _unicode_code_unit(self) -> int:
        end = self._position + 4
        digits = self._source[self._position : end]
        if len(digits) != 4 or any(digit not in _HEX_DIGITS for digit in digits):
            raise ValueError("invalid iOS strings Unicode escape")
        self._position = end
        return int(digits, 16)

    def _expect(self, expected: str) -> None:
        if self._position == self._length or self._source[self._position] != expected:
            raise ValueError("unsupported iOS strings grammar")
        self._position += 1


def parse_ios_strings(content: bytes) -> tuple[IosStringsEntry, ...]:
    """Decode and parse one bounded strings document without serialization."""
    return _StringsLexer(_decode_ios_strings(content)).parse()


def _ios_path_components(path: str) -> list[str] | None:
    if not path or path.startswith("/") or "//" in path or not path.endswith(".strings"):
        return None
    components = path.split("/")
    if any(not component or component in {".", ".."} for component in components):
        return None
    return components


def _lproj_locale_components(components: list[str]) -> list[tuple[int, str]] | None:
    locale_components: list[tuple[int, str]] = []
    for index, component in enumerate(components[:-1]):
        if not component.endswith(".lproj"):
            continue
        locale = normalize_preview_locale(component[: -len(".lproj")])
        if locale is None:
            return None
        locale_components.append((index, locale))
    return locale_components


def _ios_layout_path(path: str) -> tuple[str, str] | None:
    components = _ios_path_components(path)
    if components is None:
        return None
    locale_components = _lproj_locale_components(components)
    if locale_components is None:
        return None
    if len(locale_components) != 1:
        return None
    index, language = locale_components[0]
    templated = list(components)
    templated[index] = "{locale}.lproj"
    return language, f"ios-strings:{'/'.join(templated)}"


def _parse_ios_file(file: RepositorySourceFile) -> _IosFile:
    path_layout = _ios_layout_path(file.path)
    if path_layout is None:
        raise ValueError("ambiguous iOS strings path locale")
    entries = parse_ios_strings(file.content)
    return _IosFile(
        path=file.path,
        layout_identity=path_layout[1],
        language=path_layout[0],
        values={entry.key: entry.value for entry in entries},
    )


def _collect_ios_files(
    files: Iterable[RepositorySourceFile],
) -> tuple[dict[str, list[_IosFile]], set[str]]:
    grouped: dict[str, list[_IosFile]] = defaultdict(list)
    invalid_layouts: set[str] = set()
    seen_paths: set[str] = set()
    total_bytes = 0
    for file in sorted(files, key=lambda item: item.path):
        if not file.path.endswith(".strings"):
            continue
        path_layout = _ios_layout_path(file.path)
        hinted_identity = path_layout[1] if path_layout is not None else None
        total_bytes += len(file.content)
        if (
            len(file.content) > SOURCE_DISCOVERY_BUDGET.max_file_bytes
            or total_bytes > SOURCE_DISCOVERY_BUDGET.max_total_bytes
            or file.path in seen_paths
        ):
            if hinted_identity is not None:
                invalid_layouts.add(hinted_identity)
            continue
        seen_paths.add(file.path)
        try:
            source = _parse_ios_file(file)
        except ValueError:
            if hinted_identity is not None:
                invalid_layouts.add(hinted_identity)
            continue
        grouped[source.layout_identity].append(source)
    return grouped, invalid_layouts


def _candidate_for_layout(
    *,
    layout_identity: str,
    sources: list[_IosFile],
    repository_side: RepositorySide,
) -> PreviewLayoutCandidate | None:
    values: dict[str, dict[str, str]] = {}
    for source in sources:
        if source.language in values:
            return None
        values[source.language] = source.values
    try:
        return build_layout_candidate(
            repository_side=repository_side,
            format="ios_strings",
            layout_identity=layout_identity,
            files=(source.path for source in sources),
            values=values,
        )
    except ValueError:
        return None


def detect_ios_strings_layouts(
    files: Iterable[RepositorySourceFile],
    *,
    repository_side: RepositorySide,
) -> PreviewDetectionResult:
    """Return separate exact iOS strings path-layout candidates."""
    grouped, invalid_layouts = _collect_ios_files(files)
    candidates: list[PreviewLayoutCandidate] = []
    for layout_identity in sorted(grouped):
        if layout_identity in invalid_layouts:
            continue
        candidate = _candidate_for_layout(
            layout_identity=layout_identity,
            sources=grouped[layout_identity],
            repository_side=repository_side,
        )
        if candidate is not None:
            candidates.append(candidate)
    return PreviewDetectionResult(candidates=tuple(candidates))
