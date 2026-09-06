"""Production Android XML canonical parser adapter."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import replace
from typing import cast
from unicodedata import category
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
    StructureKind,
    canonical_issue_order,
    canonical_value_order,
)
from verboflex.localization.preview.core import normalize_preview_locale

MAX_CANONICAL_FILE_BYTES = 1_048_576
MAX_ANDROID_AGGREGATE_BYTES = 20_971_520
MAX_ANDROID_FILES = 500
MAX_ANDROID_VALUES = 5_000
MAX_ANDROID_XML_DEPTH = 12
MAX_ANDROID_STRUCTURE_NODES = 4_096
MAX_ANDROID_ISSUES = 5

_UTF8_BOM = b"\xef\xbb\xbf"
_XLIFF_NAMESPACE = "urn:oasis:names:tc:xliff:document:1.2"
_XLIFF_G_TAG = f"{{{_XLIFF_NAMESPACE}}}g"
_CDATA_TAG = object()
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
_COLLECTION_ATTRIBUTES = {"name", "translatable"}
_PLURAL_QUANTITIES = {"zero", "one", "two", "few", "many", "other"}
_STYLE_TAGS = {"b", "i", "u"}
_XLIFF_ATTRIBUTES = {"id", "example"}
_ANDROID_SIMPLE_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "'": "'",
    '"': '"',
    "\\": "\\",
    "@": "@",
    "?": "?",
}


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


class _AndroidTreeTarget:
    """ElementTree target that retains comments, PIs, CDATA, and namespaces."""

    def __init__(self) -> None:
        self._builder = StandardElementTree.TreeBuilder(insert_comments=True, insert_pis=True)
        self.namespace_uris: set[str] = set()

    def start(self, tag: str, attributes: dict[str, str]) -> Element:
        return self._builder.start(tag, attributes)

    def end(self, tag: str) -> Element:
        return self._builder.end(tag)

    def data(self, value: str) -> None:
        self._builder.data(value)

    def comment(self, value: str) -> Element:
        return self._builder.comment(value)

    def pi(self, target: str, value: str | None) -> Element:
        return self._builder.pi(target, value)

    def start_cdata(self) -> None:
        self._builder.start(_CDATA_TAG, {})

    def end_cdata(self) -> None:
        self._builder.end(_CDATA_TAG)  # type: ignore[arg-type]

    def start_namespace(self, _prefix: str | None, uri: str) -> None:
        self.namespace_uris.add(uri)

    def close(self) -> Element:
        return self._builder.close()


def parse_android_xml(parser_input: CanonicalParserInput) -> CanonicalParseResult:
    """Parse the complete bounded Android resource grammar without partial output."""
    if type(parser_input) is not CanonicalParserInput:
        return _invalid_input_failure()
    try:
        if (
            parser_input.format != "android_xml"
            or parser_input.repository_side not in {"direct", "keys", "translations"}
            or type(parser_input.content) is not bytes
        ):
            raise _UnsupportedAndroidXml
        language = _confirmed_language(parser_input)
        root, namespace_uris = _parse_root(parser_input.content)
        values = _resource_values(
            root=root,
            namespace_uris=namespace_uris,
            parser_input=parser_input,
            language=language,
        )
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


def parse_android_xml_files(
    parser_inputs: tuple[CanonicalParserInput, ...],
) -> CanonicalParseResult:
    """Combine bounded Android peer files only when every file parses successfully."""
    if type(parser_inputs) is not tuple or not parser_inputs:
        return _invalid_batch_failure()
    if any(type(item) is not CanonicalParserInput for item in parser_inputs):
        return _invalid_batch_failure()
    if any(not isinstance(item.content, bytes) for item in parser_inputs):
        return _invalid_batch_failure()
    if len(parser_inputs) > MAX_ANDROID_FILES:
        return _failure(parser_inputs[0], code="unsupported_structure")
    if sum(len(item.content) for item in parser_inputs) > MAX_ANDROID_AGGREGATE_BYTES:
        return _failure(parser_inputs[0], code="unsupported_structure")

    values: list[CanonicalValue] = []
    issues: list[CanonicalIssue] = []
    ordered_inputs = sorted(
        parser_inputs,
        key=lambda item: (item.repository_side, item.path),
    )
    for parser_input in ordered_inputs:
        result = parse_android_xml(parser_input)
        if result.issues:
            issues.extend(result.issues)
        else:
            values.extend(result.values)
        if len(values) > MAX_ANDROID_VALUES:
            return _failure(parser_input, code="unsupported_structure")
    if issues:
        unique_issues = set(issues)
        return CanonicalParseResult(
            issues=tuple(sorted(unique_issues, key=canonical_issue_order)[:MAX_ANDROID_ISSUES])
        )
    try:
        return CanonicalParseResult(values=tuple(sorted(values, key=canonical_value_order)))
    except ValueError:
        return _failure(ordered_inputs[0], code="duplicate_key")


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
    if "\ufeff" in text or any(
        category(character) == "Cc" and character not in {"\t", "\n", "\r"} for character in text
    ):
        raise _MalformedAndroidXml
    return text


def _parse_root(content: bytes) -> tuple[Element, frozenset[str]]:
    text = _decode_xml(content)
    target = _AndroidTreeTarget()
    parser = ElementTree.DefusedXMLParser(
        target=target,
        forbid_dtd=True,
        forbid_entities=True,
        forbid_external=True,
    )
    parser.parser.StartCdataSectionHandler = target.start_cdata
    parser.parser.EndCdataSectionHandler = target.end_cdata
    parser.parser.StartNamespaceDeclHandler = target.start_namespace
    try:
        root = StandardElementTree.fromstring(text, parser=parser)
    except ElementTree.ParseError as error:
        line, zero_based_column = getattr(error, "position", (None, None))
        column = zero_based_column + 1 if isinstance(zero_based_column, int) else None
        raise _MalformedAndroidXml(line=line, column=column) from error
    except DefusedXmlException as error:
        raise _MalformedAndroidXml from error
    _require_bounded_depth(root)
    return root, frozenset(target.namespace_uris)


def _resource_values(
    *,
    root: Element,
    namespace_uris: frozenset[str],
    parser_input: CanonicalParserInput,
    language: str,
) -> tuple[CanonicalValue, ...]:
    if (
        root.tag != "resources"
        or root.attrib
        or (root.text or "").strip()
        or any(uri != _XLIFF_NAMESPACE for uri in namespace_uris)
    ):
        raise _UnsupportedAndroidXml
    values: list[CanonicalValue] = []
    seen_keys: set[str] = set()
    pending_comments: list[CanonicalStructureNode] = []
    resource_position = 0
    for child in root:
        if cast(object, child.tag) is StandardElementTree.Comment:
            pending_comments.append(_comment_node(child))
            if (child.tail or "").strip():
                raise _UnsupportedAndroidXml
            continue
        if not isinstance(child.tag, str):
            raise _UnsupportedAndroidXml
        key, resource_values = _resource_value(
            child=child,
            position=resource_position,
            parser_input=parser_input,
            language=language,
            prefix=tuple(pending_comments),
        )
        pending_comments.clear()
        if key in seen_keys:
            raise _DuplicateAndroidKey
        seen_keys.add(key)
        if len(values) + len(resource_values) > MAX_ANDROID_VALUES:
            raise _UnsupportedAndroidXml
        values.extend(resource_values)
        resource_position += 1
    if pending_comments:
        if not values:
            raise _UnsupportedAndroidXml
        last = values[-1]
        structure = last.structure + tuple(pending_comments)
        if len(structure) > MAX_ANDROID_STRUCTURE_NODES:
            raise _UnsupportedAndroidXml
        values[-1] = replace(last, structure=structure)
    return tuple(values)


def _resource_value(
    *,
    child: Element,
    position: int,
    parser_input: CanonicalParserInput,
    language: str,
    prefix: tuple[CanonicalStructureNode, ...] = (),
) -> tuple[str, tuple[CanonicalValue, ...]]:
    if child.tag == "string":
        return _string_values(
            child=child,
            position=position,
            parser_input=parser_input,
            language=language,
            prefix=prefix,
        )
    if child.tag == "plurals":
        return _plural_values(
            child=child,
            position=position,
            parser_input=parser_input,
            language=language,
            prefix=prefix,
        )
    if child.tag == "string-array":
        return _array_values(
            child=child,
            position=position,
            parser_input=parser_input,
            language=language,
            prefix=prefix,
        )
    raise _UnsupportedAndroidXml


def _string_values(
    *,
    child: Element,
    position: int,
    parser_input: CanonicalParserInput,
    language: str,
    prefix: tuple[CanonicalStructureNode, ...],
) -> tuple[str, tuple[CanonicalValue, ...]]:
    _require_attributes(child, allowed=_STRING_ATTRIBUTES, required={"name"})
    if (child.tail or "").strip():
        raise _UnsupportedAndroidXml
    key = child.attrib["name"]
    _require_nonempty_text(key)
    attribute_fields = _canonical_attributes(child.attrib)
    display_text, content_nodes = _mixed_content(
        child,
        structure_prefix_size=len(prefix) + 1,
    )
    structure = (
        prefix
        + (CanonicalStructureNode(kind="android_xml:string", fields=attribute_fields),)
        + content_nodes
    )
    value = _canonical_value(
        key=key,
        language=language,
        selector=CanonicalSelector(kind="scalar", fields=()),
        display_text=display_text,
        structure=structure,
        parser_input=parser_input,
        position=position,
        structural_address=("resources", "string", position),
    )
    return key, (value,)


def _plural_values(
    *,
    child: Element,
    position: int,
    parser_input: CanonicalParserInput,
    language: str,
    prefix: tuple[CanonicalStructureNode, ...],
) -> tuple[str, tuple[CanonicalValue, ...]]:
    _require_attributes(child, allowed=_COLLECTION_ATTRIBUTES, required={"name"})
    if (child.text or "").strip() or (child.tail or "").strip():
        raise _UnsupportedAndroidXml
    key = child.attrib["name"]
    _require_nonempty_text(key)
    header = prefix + (
        CanonicalStructureNode(
            kind="android_xml:plurals",
            fields=_canonical_attributes(child.attrib),
        ),
    )
    values: list[CanonicalValue] = []
    quantities: set[str] = set()
    pending_comments: list[CanonicalStructureNode] = []
    item_position = 0
    for item in child:
        if cast(object, item.tag) is StandardElementTree.Comment:
            pending_comments.append(_comment_node(item))
            if (item.tail or "").strip():
                raise _UnsupportedAndroidXml
            continue
        if item.tag != "item":
            raise _UnsupportedAndroidXml
        _require_attributes(item, allowed={"quantity"}, required={"quantity"})
        quantity = item.attrib["quantity"]
        if quantity not in _PLURAL_QUANTITIES:
            raise _UnsupportedAndroidXml
        if quantity in quantities:
            raise _DuplicateAndroidKey
        quantities.add(quantity)
        display_text, content_nodes = _mixed_content(
            item,
            structure_prefix_size=len(header) + len(pending_comments) + 1,
        )
        structure = (
            header
            + tuple(pending_comments)
            + (
                CanonicalStructureNode(
                    kind="android_xml:item",
                    fields=(("quantity", quantity),),
                ),
            )
            + content_nodes
        )
        pending_comments.clear()
        values.append(
            _canonical_value(
                key=key,
                language=language,
                selector=CanonicalSelector(
                    kind="android_quantity",
                    fields=(("quantity", quantity),),
                ),
                display_text=display_text,
                structure=structure,
                parser_input=parser_input,
                position=position,
                structural_address=(
                    "resources",
                    "plurals",
                    position,
                    "item",
                    item_position,
                ),
            )
        )
        item_position += 1
    _require_nonempty_collection(values, pending_comments)
    return key, tuple(values)


def _array_values(
    *,
    child: Element,
    position: int,
    parser_input: CanonicalParserInput,
    language: str,
    prefix: tuple[CanonicalStructureNode, ...],
) -> tuple[str, tuple[CanonicalValue, ...]]:
    _require_attributes(child, allowed=_COLLECTION_ATTRIBUTES, required={"name"})
    if (child.text or "").strip() or (child.tail or "").strip():
        raise _UnsupportedAndroidXml
    key = child.attrib["name"]
    _require_nonempty_text(key)
    header = prefix + (
        CanonicalStructureNode(
            kind="android_xml:string_array",
            fields=_canonical_attributes(child.attrib),
        ),
    )
    values: list[CanonicalValue] = []
    pending_comments: list[CanonicalStructureNode] = []
    item_position = 0
    for item in child:
        if cast(object, item.tag) is StandardElementTree.Comment:
            pending_comments.append(_comment_node(item))
            if (item.tail or "").strip():
                raise _UnsupportedAndroidXml
            continue
        if item.tag != "item" or item.attrib:
            raise _UnsupportedAndroidXml
        if item_position >= MAX_ANDROID_VALUES:
            raise _UnsupportedAndroidXml
        display_text, content_nodes = _mixed_content(
            item,
            structure_prefix_size=len(header) + len(pending_comments) + 1,
        )
        structure = (
            header
            + tuple(pending_comments)
            + (
                CanonicalStructureNode(
                    kind="android_xml:item",
                    fields=(("index", item_position),),
                ),
            )
            + content_nodes
        )
        pending_comments.clear()
        values.append(
            _canonical_value(
                key=key,
                language=language,
                selector=CanonicalSelector(
                    kind="android_array_item",
                    fields=(("index", item_position),),
                ),
                display_text=display_text,
                structure=structure,
                parser_input=parser_input,
                position=position,
                structural_address=(
                    "resources",
                    "string-array",
                    position,
                    "item",
                    item_position,
                ),
            )
        )
        item_position += 1
    _require_nonempty_collection(values, pending_comments)
    return key, tuple(values)


def _canonical_value(
    *,
    key: str,
    language: str,
    selector: CanonicalSelector,
    display_text: str,
    structure: tuple[CanonicalStructureNode, ...],
    parser_input: CanonicalParserInput,
    position: int,
    structural_address: tuple[str | int, ...],
) -> CanonicalValue:
    source_text, translated_text = _side_texts(
        repository_side=parser_input.repository_side,
        language=language,
        base_language=parser_input.base_language,
        text=display_text,
    )
    return CanonicalValue(
        logical_key=key,
        language=language,
        selector=selector,
        source_text=source_text,
        translated_text=translated_text,
        display_text=display_text,
        structure=structure,
        locator=CanonicalLocator(
            format="android_xml",
            repository_side=parser_input.repository_side,
            path=parser_input.path,
            position=position,
            structural_address=structural_address,
        ),
    )


def _mixed_content(
    element: Element,
    *,
    structure_prefix_size: int,
) -> tuple[str, tuple[CanonicalStructureNode, ...]]:
    nodes: list[CanonicalStructureNode] = []
    visible: list[str] = []
    cdata_ordinal = [0]
    _append_text_node(
        nodes,
        visible,
        kind="android_xml:text",
        raw=element.text or "",
        structure_prefix_size=structure_prefix_size,
    )
    for child in element:
        _append_mixed_child(
            child,
            nodes=nodes,
            visible=visible,
            cdata_ordinal=cdata_ordinal,
            structure_prefix_size=structure_prefix_size,
        )
    return "".join(visible), tuple(nodes)


def _append_mixed_child(
    child: Element,
    *,
    nodes: list[CanonicalStructureNode],
    visible: list[str],
    cdata_ordinal: list[int],
    structure_prefix_size: int,
) -> None:
    if child.tag is _CDATA_TAG:
        raw = child.text or ""
        decoded = _decode_android_escapes(raw)
        _append_structure_node(
            nodes,
            CanonicalStructureNode(
                kind="android_xml:cdata",
                fields=(("value", raw), ("ordinal", cdata_ordinal[0])),
            ),
            structure_prefix_size=structure_prefix_size,
        )
        cdata_ordinal[0] += 1
        visible.append(decoded)
    elif cast(object, child.tag) is StandardElementTree.Comment:
        _append_structure_node(
            nodes,
            _comment_node(child),
            structure_prefix_size=structure_prefix_size,
        )
    elif cast(object, child.tag) is StandardElementTree.ProcessingInstruction:
        raise _UnsupportedAndroidXml
    elif isinstance(child.tag, str):
        start_fields, end_fields = _inline_fields(child)
        _append_structure_node(
            nodes,
            CanonicalStructureNode(kind="android_xml:inline", fields=start_fields),
            structure_prefix_size=structure_prefix_size,
        )
        _append_text_node(
            nodes,
            visible,
            kind="android_xml:text",
            raw=child.text or "",
            structure_prefix_size=structure_prefix_size,
        )
        for nested in child:
            _append_mixed_child(
                nested,
                nodes=nodes,
                visible=visible,
                cdata_ordinal=cdata_ordinal,
                structure_prefix_size=structure_prefix_size,
            )
        _append_structure_node(
            nodes,
            CanonicalStructureNode(kind="android_xml:inline", fields=end_fields),
            structure_prefix_size=structure_prefix_size,
        )
    else:
        raise _UnsupportedAndroidXml
    if child.tail:
        _append_text_node(
            nodes,
            visible,
            kind="android_xml:tail",
            raw=child.tail,
            structure_prefix_size=structure_prefix_size,
        )


def _append_text_node(
    nodes: list[CanonicalStructureNode],
    visible: list[str],
    *,
    kind: str,
    raw: str,
    structure_prefix_size: int,
) -> None:
    decoded = _decode_android_escapes(raw)
    _append_structure_node(
        nodes,
        CanonicalStructureNode(
            kind=cast(StructureKind, kind),
            fields=(("value", raw),),
        ),
        structure_prefix_size=structure_prefix_size,
    )
    visible.append(decoded)


def _append_structure_node(
    nodes: list[CanonicalStructureNode],
    node: CanonicalStructureNode,
    *,
    structure_prefix_size: int,
) -> None:
    if structure_prefix_size + len(nodes) >= MAX_ANDROID_STRUCTURE_NODES:
        raise _UnsupportedAndroidXml
    nodes.append(node)


def _inline_fields(
    child: Element,
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    if child.tag in _STYLE_TAGS:
        if child.attrib:
            raise _UnsupportedAndroidXml
        return (
            (("event", "start"), ("name", child.tag)),
            (("event", "end"), ("name", child.tag)),
        )
    if child.tag != _XLIFF_G_TAG:
        raise _UnsupportedAndroidXml
    _require_attributes(child, allowed=_XLIFF_ATTRIBUTES, required={"id"})
    identifier = child.attrib["id"]
    _require_nonempty_text(identifier)
    start_fields: list[tuple[str, str]] = [
        ("event", "start"),
        ("name", "g"),
        ("namespace", _XLIFF_NAMESPACE),
        ("id", identifier),
    ]
    example = child.attrib.get("example")
    if example is not None:
        if _contains_forbidden_control(example):
            raise _UnsupportedAndroidXml
        start_fields.append(("example", example))
    return (
        tuple(start_fields),
        (("event", "end"), ("name", "g"), ("namespace", _XLIFF_NAMESPACE)),
    )


def _decode_android_escapes(raw: str) -> str:
    if _contains_forbidden_control(raw):
        raise _UnsupportedAndroidXml
    decoded: list[str] = []
    index = 0
    while index < len(raw):
        character = raw[index]
        if character != "\\":
            decoded.append(character)
            index += 1
            continue
        if index + 1 >= len(raw):
            raise _UnsupportedAndroidXml
        escape = raw[index + 1]
        simple = _ANDROID_SIMPLE_ESCAPES.get(escape)
        if simple is not None:
            decoded.append(simple)
            index += 2
            continue
        if escape != "u" or index + 6 > len(raw):
            raise _UnsupportedAndroidXml
        token = raw[index + 2 : index + 6]
        if not all(character in "0123456789abcdefABCDEF" for character in token):
            raise _UnsupportedAndroidXml
        codepoint = int(token, 16)
        index += 6
        if 0xD800 <= codepoint <= 0xDBFF:
            if index + 6 > len(raw) or raw[index : index + 2] != "\\u":
                raise _UnsupportedAndroidXml
            low_token = raw[index + 2 : index + 6]
            if not all(character in "0123456789abcdefABCDEF" for character in low_token):
                raise _UnsupportedAndroidXml
            low = int(low_token, 16)
            if not 0xDC00 <= low <= 0xDFFF:
                raise _UnsupportedAndroidXml
            codepoint = 0x10000 + ((codepoint - 0xD800) << 10) + (low - 0xDC00)
            index += 6
        elif 0xDC00 <= codepoint <= 0xDFFF:
            raise _UnsupportedAndroidXml
        decoded.append(chr(codepoint))
    return "".join(decoded)


def _require_attributes(
    element: Element,
    *,
    allowed: set[str],
    required: set[str],
) -> None:
    names = set(element.attrib)
    if not required.issubset(names) or not names.issubset(allowed):
        raise _UnsupportedAndroidXml


def _require_nonempty_text(value: str) -> None:
    if not value or _contains_forbidden_control(value):
        raise _UnsupportedAndroidXml


def _require_nonempty_collection(
    values: list[CanonicalValue],
    pending_comments: list[CanonicalStructureNode],
) -> None:
    if not values or pending_comments:
        raise _UnsupportedAndroidXml


def _comment_node(element: Element) -> CanonicalStructureNode:
    value = element.text or ""
    if _contains_forbidden_control(value):
        raise _UnsupportedAndroidXml
    return CanonicalStructureNode(
        kind="android_xml:comment",
        fields=(("value", value),),
    )


def _contains_forbidden_control(value: str) -> bool:
    return any(
        category(character) == "Cc" and character not in {"\t", "\n", "\r"} for character in value
    )


def _require_bounded_depth(root: Element) -> None:
    stack: list[tuple[Element, int]] = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        if depth > MAX_ANDROID_XML_DEPTH:
            raise _UnsupportedAndroidXml
        stack.extend((child, depth + 1) for child in element)


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
    repository_side = (
        parser_input.repository_side
        if parser_input.repository_side in {"direct", "keys", "translations"}
        else "direct"
    )
    path = parser_input.path if _is_safe_relative_path(parser_input.path) else "<input>"
    return CanonicalParseResult(
        issues=(
            CanonicalIssue(
                code=code,
                repository_side=repository_side,
                path=path,
                message=messages[code],
                line=line,
                column=column,
            ),
        )
    )


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


def _invalid_batch_failure() -> CanonicalParseResult:
    return CanonicalParseResult(
        issues=(
            CanonicalIssue(
                code="malformed_file",
                repository_side="direct",
                path="<input>",
                message="Malformed Android XML input batch.",
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
                message="Malformed Android XML parser input.",
            ),
        )
    )
