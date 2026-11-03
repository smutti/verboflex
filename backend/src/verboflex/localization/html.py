"""Bounded HTML text indexing; source markup is never reserialized."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import PurePosixPath

from babel import Locale, UnknownLocaleError

from verboflex.localization.preview.core import normalize_preview_locale

_FILENAME = re.compile(r"^(.+?)([-_])([A-Z]{2,3}(?:-[A-Z]{2})?)\.(html?)$", re.I)
_VOID = frozenset(
    [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ]
)
_IGNORED = frozenset({"style", "script"})
_VARIABLE = re.compile(r"\{\{\s*[A-Za-z_][A-Za-z0-9_.]*\s*\}\}")


def html_path(path: str) -> tuple[str, str, str] | None:
    """Return locale, locale-independent relative family, and suffix separator."""
    item = PurePosixPath(path)
    for pattern in (_FILENAME, re.compile(r"^(.+)([-_])([A-Z]{2,3})\.(html?)$", re.I)):
        match = pattern.fullmatch(item.name)
        if match is None:
            continue
        language = normalize_preview_locale(match[3])
        if language is None:
            continue
        try:
            Locale.parse(language, sep="-")
        except ValueError, UnknownLocaleError:
            continue
        return language, str(item.with_name(match[1])), match[2]
    return None


def html_variables(text: str) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(_VARIABLE.findall(text)).items()))


def valid_html_replacement(source: str, replacement: str) -> bool:
    # Empty fragments would erase their structural identity on the next import.
    return (
        bool(replacement.strip())
        and replacement == replacement.strip(" \t\r\n")
        and not any(ord(char) < 32 and char not in "\t\r\n" for char in replacement)
        and html_variables(source) == html_variables(replacement)
        and "{{" not in _VARIABLE.sub("", replacement)
        and "}}" not in _VARIABLE.sub("", replacement)
    )


@dataclass(frozen=True, slots=True)
class HtmlText:
    address: str
    element: str
    start: int
    end: int
    text: str


class _Index(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=False)
        self.text = text
        self.lines = [0]
        self.lines.extend(match.end() for match in re.finditer("\n", text))
        self.stack: list[tuple[str, str, int]] = []
        self.children: Counter[str] = Counter()
        self.slots: Counter[str] = Counter()
        self.spans: list[tuple[str, str, int, int]] = []
        self.pending: tuple[int, int] | None = None
        self.saw_html = False
        self.node_count = 0

    def source_offset(self) -> int:
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def flush(self) -> None:
        if self.pending is None:
            return
        start, end = self.pending
        self.pending = None
        if not self.stack or any(tag in _IGNORED for tag, _, _ in self.stack):
            return
        raw = self.text[start:end]
        if not unescape(raw).strip():
            return
        # Keep indentation and boundary spaces outside the editable byte span.
        start += len(raw) - len(raw.lstrip(" \t\r\n"))
        end -= len(raw) - len(raw.rstrip(" \t\r\n"))
        tag, path, _ = self.stack[-1]
        slot = self.slots[path]
        self.slots[path] += 1
        self.spans.append((f"{path}/text[{slot}]", tag, start, end))
        if len(self.spans) > 5000:
            raise ValueError("Too many HTML text fragments")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.flush()
        parent = self.stack[-1][1] if self.stack else ""
        key = f"{parent}/{tag}"
        index = self.children[key]
        self.children[key] += 1
        if tag == "html":
            self.saw_html = True
        if tag not in _VOID:
            self.stack.append((tag, f"{key}[{index}]", self.source_offset()))
        self.node_count += 1
        if len(self.stack) > 64 or self.node_count > 20000:
            raise ValueError("HTML structure exceeds bounds")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        self.flush()
        if not self.stack or self.stack[-1][0] != tag:
            raise ValueError("Unbalanced HTML tags")
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        start = self.source_offset()
        if self.pending is not None and self.pending[1] != start:
            self.flush()
        self.pending = (self.pending[0] if self.pending else start, start + len(data))

    def handle_entityref(self, name: str) -> None:
        self.handle_data(self._reference(name))

    def handle_charref(self, name: str) -> None:
        self.handle_data(self._reference("#" + name))

    def _reference(self, name: str) -> str:
        raw = "&" + name
        return raw + (";" if self.text[self.source_offset() + len(raw) :].startswith(";") else "")

    def handle_comment(self, data: str) -> None:
        self.flush()

    def handle_decl(self, decl: str) -> None:
        self.flush()
        if decl.lower() != "doctype html":
            raise ValueError("Unsupported HTML declaration")

    def unknown_decl(self, data: str) -> None:
        raise ValueError("Unsupported HTML declaration")

    def handle_pi(self, data: str) -> None:
        raise ValueError("Unsupported HTML processing instruction")


def index_html(content: bytes) -> tuple[tuple[HtmlText, ...], str]:
    if not content or len(content) > 1048576 or b"\x00" in content:
        raise ValueError("Invalid HTML input")
    text = content.decode("utf-8")
    parser = _Index(text)
    parser.feed(text)
    parser.close()
    parser.flush()
    if parser.stack or not parser.saw_html or not parser.spans:
        raise ValueError("Incomplete HTML document")
    offsets = [0]
    for char in text:
        offsets.append(offsets[-1] + len(char.encode("utf-8")))
    values = tuple(
        HtmlText(address, element, offsets[start], offsets[end], unescape(text[start:end]))
        for address, element, start, end in parser.spans
    )
    protected = bytearray()
    cursor = 0
    for value in values:
        protected.extend(content[cursor : value.start])
        protected.extend(b"\x00TEXT\x00")
        cursor = value.end
    protected.extend(content[cursor:])
    return values, hashlib.sha256(protected).hexdigest()


def html_skeleton(content: bytes, fragments: tuple[HtmlText, ...]) -> str:
    if b"<!--VERBOFLEX-TEXT:" in content:
        raise ValueError("Reserved HTML preview marker")
    parts: list[bytes] = []
    cursor = 0
    for position, fragment in enumerate(fragments):
        parts.extend(
            (content[cursor : fragment.start], f"<!--VERBOFLEX-TEXT:{position}-->".encode())
        )
        cursor = fragment.end
    parts.append(content[cursor:])
    return b"".join(parts).decode("utf-8")
