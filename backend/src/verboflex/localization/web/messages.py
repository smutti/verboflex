"""ngx-translate parameters and explicitly declared rich-text contracts."""

import re
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlsplit

_TOKEN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*\}\}")
_ICU = re.compile(r"\{\s*\w+\s*,\s*(?:plural|select|selectordinal)\b")
_TAGS = {"a", "b", "strong", "i", "em", "u", "br", "p", "span", "ul", "ol", "li"}


class WebMessageInvalid(ValueError):
    """A message no longer satisfies its imported source contract."""


def parameters(text: str) -> Counter[str]:
    if _ICU.search(text) or "\\{{" in text or len(text) > 65536:
        raise WebMessageInvalid("Unsupported message syntax")
    remainder = _TOKEN.sub("", text)
    if "{{" in remainder or "}}" in remainder:
        raise WebMessageInvalid("Malformed interpolation parameter")
    return Counter(match.group(1) for match in _TOKEN.finditer(text))


class _Markup(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=False)
        self.structure: list[tuple[str, str, tuple[tuple[str, str | None], ...]]] = []
        self.stack: list[str] = []
        self.feed(text)
        self.close()
        if self.stack:
            raise WebMessageInvalid("Unclosed markup")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _TAGS or any(k not in {"class", "href", "target", "rel"} for k, _ in attrs):
            raise WebMessageInvalid("Unsupported markup")
        if len({key for key, _ in attrs}) != len(attrs):
            raise WebMessageInvalid("Duplicate markup attribute")
        for key, value in attrs:
            if key == "href" and (
                value is None
                or any(ord(c) < 32 for c in value)
                or urlsplit(value.strip()).scheme.lower() not in {"", "https", "http", "mailto"}
            ):
                raise WebMessageInvalid("Unsupported link")
        self.structure.append(("open", tag, tuple(sorted(attrs))))
        if tag != "br":
            self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag != "br":
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack.pop() != tag:
            raise WebMessageInvalid("Invalid markup nesting")
        self.structure.append(("close", tag, ()))

    def handle_comment(self, data: str) -> None:
        raise WebMessageInvalid("Comments are not translation text")

    def handle_decl(self, decl: str) -> None:
        raise WebMessageInvalid("Declarations are not translation text")

    def handle_pi(self, data: str) -> None:
        raise WebMessageInvalid("Instructions are not translation text")


def validate_message(source: str, target: str, *, rich_text: bool = False) -> None:
    if parameters(source) != parameters(target):
        raise WebMessageInvalid("Translation parameters must match the source")
    before, after = _Markup(source).structure, _Markup(target).structure
    if (not rich_text and (before or after)) or before != after:
        raise WebMessageInvalid("Translation markup must match the source")
