"""Passive preview markup only; never used to serialize repository files."""

from html import escape
from html.parser import HTMLParser

_TAGS = frozenset(
    {
        "html",
        "head",
        "body",
        "title",
        "style",
        "div",
        "span",
        "p",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "td",
        "th",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "b",
        "strong",
        "i",
        "em",
        "u",
        "s",
        "small",
        "br",
        "hr",
        "center",
        "ul",
        "ol",
        "li",
        "a",
        "img",
    }
)
_ATTRIBUTES = frozenset(
    {
        "style",
        "class",
        "id",
        "width",
        "height",
        "align",
        "valign",
        "bgcolor",
        "cellpadding",
        "cellspacing",
        "border",
        "role",
        "dir",
        "lang",
        "alt",
        "colspan",
        "rowspan",
        "aria-label",
    }
)
_SUPPRESS = frozenset({"script", "iframe", "object", "template", "noscript"})


class _PassiveHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.suppressed = 0
        self.in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SUPPRESS:
            self.suppressed += 1
        if self.suppressed or tag not in _TAGS:
            return
        if tag == "style":
            self.in_style = True
        attributes = "".join(
            f' {name}="{escape(value, quote=True)}"'
            for name, value in attrs
            if name in _ATTRIBUTES and value is not None
        )
        self.parts.append(f"<{tag}{attributes}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self.in_style = False
        if tag in _SUPPRESS:
            self.suppressed = max(0, self.suppressed - 1)
            return
        if not self.suppressed and tag in _TAGS and tag not in {"br", "hr", "img"}:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.parts.append(data if self.in_style else escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        if not self.suppressed:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self.suppressed:
            self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        # Only the application-owned editing placeholder survives preview sanitization.
        if data == "VERBOFLEX-SELECTED-TEXT" and not self.suppressed:
            self.parts.append("<!--VERBOFLEX-SELECTED-TEXT-->")


def passive_html_preview(document: str) -> str:
    parser = _PassiveHtml()
    parser.feed(document)
    parser.close()
    return "".join(parser.parts)
