"""Production Android XML canonical parser adapter."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast
from xml.etree import ElementTree as StandardElementTree
from xml.etree.ElementTree import Element

from defusedxml import ElementTree  # type: ignore[import-untyped]
from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]

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
from verboflex.localization.preview.core import normalize_preview_locale

MAX_CANONICAL_FILE_BYTES = 1_048_576

_UTF8_BOM = b"\xef\xbb\xbf"
_XML_DECLARATION = re.compile(
    r"\A<\?xml\s+version\s*=\s*(['\"])1\.0\1"
    r"(?:\s+encoding\s*=\s*(['\"])(?P<encoding>[^'\"]+)\2)?"
    r"(?:\s+standalone\s*=\s*(['\"])(?:yes|no)\3)?\s*\?>",
    re.IGNORECASE,
)
_ANDROID_PATH = re.compile(
    r"\A(?:(?P<prefix>.+)/)?res/values(?:-(?P<language>[A-Za-z]{2,3}))?/"
    r"(?P<filename>[^/]+\.xml)\Z"
)
_BOOLEAN_ATTRIBUTES = {"true": True, "false": False}
_STRING_ATTRIBUTES = {"name", "translatable", "formatted"}


class _MalformedAndroidXml(ValueError):
    def __init__(self, *, line: int | None = None, column: int | None = None) -> None:
        super().__init__("malformed Android XML")
        self.line = line
        self.column = column


class _UnsupportedAndroidXml(ValueError):
    pass


class _AmbiguousAndroidLayout(ValueError):
    pass


class _DuplicateAndroidKey(ValueError):
    pass


def parse_android_xml(parser_input: CanonicalParserInput) -> CanonicalParseResult:
    """Parse the Phase 4 scalar tracer grammar without partial output."""
    try:
        language = _confirmed_language(parser_input)
        root = _parse_root(parser_input.content)
        values = _scalar_values(root=root, parser_input=parser_input, language=language)
    except _MalformedAndroidXml as error:
        return _failure(
            parser_input,
            code="malformed_file",
            line=error.line,
            column=error.column,
        )
    except _DuplicateAndroidKey:
        return _failure(parser_input, code="duplicate_key")
    except _AmbiguousAndroidLayout:
        return _failure(parser_input, code="ambiguous_structure")
    except _UnsupportedAndroidXml:
        return _failure(parser_input, code="unsupported_structure")
    return CanonicalParseResult(values=tuple(sorted(values, key=canonical_value_order)))


def _confirmed_language(parser_input: CanonicalParserInput) -> str:
    match = _ANDROID_PATH.fullmatch(parser_input.path)
    if match is None:
        raise _UnsupportedAndroidXml
    prefix = match.group("prefix")
    path_layout = f"{prefix}/res" if prefix else "res"
    if path_layout != parser_input.layout_identity or parser_input.layout_version != 1:
        raise _AmbiguousAndroidLayout
    path_language = match.group("language")
    if path_language is None:
        language = normalize_preview_locale(parser_input.base_language)
    else:
        language = normalize_preview_locale(path_language)
    if language is None:
        raise _UnsupportedAndroidXml
    return language


def _decode_xml(content: bytes) -> str:
    if len(content) > MAX_CANONICAL_FILE_BYTES:
        raise _MalformedAndroidXml
    if content.startswith((b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00", b"\xff\xfe", b"\xfe\xff")):
        raise _MalformedAndroidXml
    raw = content[len(_UTF8_BOM) :] if content.startswith(_UTF8_BOM) else content
    if not raw or b"\x00" in raw:
        raise _MalformedAndroidXml
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise _MalformedAndroidXml from error
    if text.startswith("<?xml"):
        declaration = _XML_DECLARATION.match(text)
        if declaration is None:
            raise _MalformedAndroidXml
        encoding = declaration.group("encoding")
        if encoding is not None and encoding.casefold() != "utf-8":
            raise _MalformedAndroidXml
    return text


def _parse_root(content: bytes) -> Element:
    text = _decode_xml(content)
    parser = ElementTree.DefusedXMLParser(
        target=StandardElementTree.TreeBuilder(insert_comments=True, insert_pis=True),
        forbid_dtd=True,
        forbid_entities=True,
        forbid_external=True,
    )
    try:
        return StandardElementTree.fromstring(text, parser=parser)
    except ElementTree.ParseError as error:
        line, zero_based_column = getattr(error, "position", (None, None))
        column = zero_based_column + 1 if isinstance(zero_based_column, int) else None
        raise _MalformedAndroidXml(line=line, column=column) from error
    except DefusedXmlException as error:
        raise _MalformedAndroidXml from error


def _scalar_values(
    *,
    root: Element,
    parser_input: CanonicalParserInput,
    language: str,
) -> tuple[CanonicalValue, ...]:
    if root.tag != "resources" or root.attrib or (root.text or "").strip():
        raise _UnsupportedAndroidXml
    values: list[CanonicalValue] = []
    seen_keys: set[str] = set()
    for position, child in enumerate(root):
        value = _scalar_value(
            child=child,
            position=position,
            parser_input=parser_input,
            language=language,
        )
        if value.logical_key in seen_keys:
            raise _DuplicateAndroidKey
        seen_keys.add(value.logical_key)
        values.append(value)
    if not values:
        raise _UnsupportedAndroidXml
    return tuple(values)


def _scalar_value(
    *,
    child: Element,
    position: int,
    parser_input: CanonicalParserInput,
    language: str,
) -> CanonicalValue:
    if (
        child.tag != "string"
        or not isinstance(child.tag, str)
        or not set(child.attrib).issubset(_STRING_ATTRIBUTES)
        or "name" not in child.attrib
        or len(child) != 0
        or (child.tail or "").strip()
    ):
        raise _UnsupportedAndroidXml
    key = child.attrib["name"]
    text = child.text or ""
    if not key or "\x00" in key or "\x00" in text:
        raise _UnsupportedAndroidXml
    attribute_fields = _canonical_attributes(child.attrib)
    source_text, translated_text = _side_texts(
        repository_side=parser_input.repository_side,
        language=language,
        base_language=parser_input.base_language,
        text=text,
    )
    return CanonicalValue(
        logical_key=key,
        language=language,
        selector=CanonicalSelector(kind="scalar", fields=()),
        source_text=source_text,
        translated_text=translated_text,
        display_text=text,
        structure=(
            CanonicalStructureNode(kind="android_xml:string", fields=attribute_fields),
            CanonicalStructureNode(kind="android_xml:text", fields=(("value", text),)),
        ),
        locator=CanonicalLocator(
            format="android_xml",
            repository_side=parser_input.repository_side,
            path=parser_input.path,
            position=position,
            structural_address=("resources", "string", position),
        ),
    )


def _canonical_attributes(attributes: Mapping[str, str]) -> tuple[tuple[str, bool], ...]:
    fields: list[tuple[str, bool]] = []
    for name in ("translatable", "formatted"):
        raw = attributes.get(name)
        if raw is None:
            continue
        value = _BOOLEAN_ATTRIBUTES.get(raw)
        if value is None:
            raise _UnsupportedAndroidXml
        fields.append((name, value))
    return tuple(fields)


def _side_texts(
    *,
    repository_side: str,
    language: str,
    base_language: str,
    text: str,
) -> tuple[str | None, str | None]:
    normalized_base = normalize_preview_locale(base_language)
    if repository_side == "keys" or (repository_side == "direct" and language == normalized_base):
        return text, None
    return None, text


def _failure(
    parser_input: CanonicalParserInput,
    *,
    code: IssueCode,
    line: int | None = None,
    column: int | None = None,
) -> CanonicalParseResult:
    messages = {
        "malformed_file": "Malformed Android XML file.",
        "ambiguous_structure": "Ambiguous Android XML structure.",
        "unsupported_structure": "Unsupported Android XML structure.",
        "duplicate_key": "Duplicate Android resource key.",
        "base_language_required": "Base language is required.",
    }
    return CanonicalParseResult(
        issues=(
            CanonicalIssue(
                code=code,
                repository_side=cast(RepositorySide, parser_input.repository_side),
                path=parser_input.path,
                message=messages[code],
                line=line,
                column=column,
            ),
        )
    )
