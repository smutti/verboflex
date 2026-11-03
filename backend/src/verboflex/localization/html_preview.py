"""Passive preview markup only; never used to serialize repository files."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser

from verboflex.localization.html_images import (
    MAX_PREVIEW_IMAGE_CHARACTERS,
    is_image_data_uri,
    repository_image_path,
)


@dataclass(frozen=True)
class HtmlPreview:
    document: str
    missing_images: int


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
    def __init__(
        self, template_path: str, images: Mapping[str, str], markers: frozenset[str]
    ) -> None:
        super().__init__(convert_charrefs=False)
        self.template_path = template_path
        self.images = images
        self.missing_images = 0
        self.image_characters = 0
        self.parts: list[str] = []
        self.suppressed = 0
        self.in_style = False
        self.markers = markers

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
        for name, value in attrs:
            if value is None or not (name == "background" or (tag == "img" and name == "src")):
                continue
            path = repository_image_path(self.template_path, value)
            if path is None:
                continue
            uri = self.images.get(path)
            if (
                uri is not None
                and is_image_data_uri(uri)
                and self.image_characters + len(uri) <= MAX_PREVIEW_IMAGE_CHARACTERS
            ):
                attributes += f' {name}="{uri}"'
                self.image_characters += len(uri)
            else:
                self.missing_images += 1
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
            safe = data if self.in_style else escape(data, quote=False)
            # HTMLParser treats title contents as RCDATA. Preserve only the
            # caller-owned placeholders there, not arbitrary source markup.
            if not self.in_style:
                safe = re.sub(
                    r"&lt;!--([^<>]*?)--&gt;",
                    lambda match: f"<!--{match[1]}-->" if match[1] in self.markers else match[0],
                    safe,
                )
            self.parts.append(safe)

    def handle_entityref(self, name: str) -> None:
        if not self.suppressed:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self.suppressed:
            self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        # Only the application-owned editing placeholder survives preview sanitization.
        if data in self.markers and not self.suppressed:
            self.parts.append(f"<!--{data}-->")


def passive_html_preview(
    document: str,
    *,
    template_path: str = "",
    images: Mapping[str, str] | None = None,
    markers: frozenset[str] = frozenset({"VERBOFLEX-SELECTED-TEXT"}),
) -> HtmlPreview:
    parser = _PassiveHtml(template_path, images or {}, markers)
    parser.feed(document)
    parser.close()
    return HtmlPreview(document="".join(parser.parts), missing_images=parser.missing_images)
