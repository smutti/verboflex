"""Bounded lexical XML positions; never serialize an XML tree to obtain edits."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from xml.parsers import expat

from verboflex.localization.importing.core import (
    MAX_CANONICAL_DEPTH,
    MAX_CANONICAL_FILE_BYTES,
    MAX_CANONICAL_STRUCTURE_NODES,
)
from verboflex.localization.writing.core import ByteEdit, WritebackReason, WritebackRejected


@dataclass(frozen=True, slots=True)
class XmlTextSpan:
    start: int
    end: int
    kind: Literal["text", "cdata", "comment"]


@dataclass(frozen=True, slots=True)
class XmlElementSpan:
    name: str
    attributes: tuple[tuple[str, str], ...] = field(repr=False)
    start: int
    start_tag_end: int
    end_tag_start: int
    end: int
    self_closing: bool
    children: tuple[XmlElementSpan, ...] = field(repr=False)
    text_spans: tuple[XmlTextSpan, ...] = field(repr=False)


@dataclass(slots=True)
class _Node:
    name: str
    attributes: tuple[tuple[str, str], ...] = field(repr=False)
    start: int
    start_tag_end: int
    self_closing: bool
    end_tag_start: int = 0
    end: int = 0
    children: list[_Node] = field(default_factory=list, repr=False)
    regions: list[XmlTextSpan] = field(default_factory=list, repr=False)


def tag_end(content: bytes, start: int) -> int:
    quote: int | None = None
    for index in range(start + 1, len(content)):
        character = content[index]
        if quote is None and character in (34, 39):
            quote = character
        elif quote == character:
            quote = None
        elif quote is None and character == 62:
            return index + 1
    raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)


def index_xml(content: bytes, *, allow_ts_doctype: bool = False) -> XmlElementSpan:
    """Index hardened-parser-approved bytes, with independent entity and resource guards."""
    if type(content) is not bytes or len(content) > MAX_CANONICAL_FILE_BYTES:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    parser = expat.ParserCreate()
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    stack: list[_Node] = []
    root: _Node | None = None
    node_count = 0
    cdata_start: int | None = None

    def reject(*_arguments: object) -> None:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)

    def doctype(name: str, system: str | None, public: str | None, subset: int) -> None:
        if not allow_ts_doctype or name != "TS" or system or public or subset:
            reject()

    def start(name: str, attributes: dict[str, str]) -> None:
        nonlocal root, node_count
        node_count += 1
        if len(stack) >= MAX_CANONICAL_DEPTH or node_count > MAX_CANONICAL_STRUCTURE_NODES:
            raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
        offset = parser.CurrentByteIndex
        end = tag_end(content, offset)
        node = _Node(name, tuple(attributes.items()), offset, end, content[end - 2 : end] == b"/>")
        if stack:
            stack[-1].children.append(node)
        else:
            root = node
        stack.append(node)

    def end(_name: str) -> None:
        node = stack.pop()
        if node.self_closing:
            node.end_tag_start = node.end = node.start_tag_end
        else:
            node.end_tag_start = parser.CurrentByteIndex
            node.end = tag_end(content, node.end_tag_start)

    def comment(_text: str) -> None:
        if stack:
            offset = parser.CurrentByteIndex
            end = content.find(b"-->", offset + 4)
            if end < 0:
                reject()
            stack[-1].regions.append(XmlTextSpan(offset, end + 3, "comment"))

    def cdata_begin() -> None:
        nonlocal cdata_start
        cdata_start = parser.CurrentByteIndex

    def cdata_end() -> None:
        nonlocal cdata_start
        if not stack or cdata_start is None:
            reject()
        assert cdata_start is not None
        stack[-1].regions.append(XmlTextSpan(cdata_start, parser.CurrentByteIndex + 3, "cdata"))
        cdata_start = None

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CommentHandler = comment
    parser.StartCdataSectionHandler = cdata_begin
    parser.EndCdataSectionHandler = cdata_end
    parser.StartDoctypeDeclHandler = doctype
    parser.EntityDeclHandler = reject
    parser.ProcessingInstructionHandler = reject
    try:
        parser.Parse(content, True)
    except expat.ExpatError:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE) from None
    if root is None or stack:
        reject()
    assert root is not None
    return _freeze(root)


def _freeze(node: _Node) -> XmlElementSpan:
    children = tuple(_freeze(child) for child in node.children)
    regions = sorted(
        [(child.start, child.end, None) for child in children]
        + [(region.start, region.end, region) for region in node.regions],
        key=lambda region: region[0],
    )
    spans: list[XmlTextSpan] = []
    cursor = node.start_tag_end
    for start, end, region in regions:
        if start > cursor:
            spans.append(XmlTextSpan(cursor, start, "text"))
        if region is not None:
            spans.append(
                XmlTextSpan(start + 9, end - 3, "cdata") if region.kind == "cdata" else region
            )
        cursor = end
    if cursor < node.end_tag_start:
        spans.append(XmlTextSpan(cursor, node.end_tag_start, "text"))
    return XmlElementSpan(
        node.name,
        node.attributes,
        node.start,
        node.start_tag_end,
        node.end_tag_start,
        node.end,
        node.self_closing,
        children,
        tuple(spans),
    )


def editable_leaf(
    node: XmlElementSpan, *, allow_styles: bool
) -> tuple[XmlElementSpan, XmlTextSpan]:
    """Accept one text slot, retaining comments and style wrappers exactly."""
    candidates: list[tuple[XmlElementSpan, XmlTextSpan]] = []

    def visit(current: XmlElementSpan) -> None:
        visible = tuple(span for span in current.text_spans if span.kind != "comment")
        candidates.extend((current, span) for span in visible)
        for child in current.children:
            if not allow_styles or child.name not in {"b", "i", "u"}:
                raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
            visit(child)
        if not visible and not current.children:
            candidates.append(
                (current, XmlTextSpan(current.start_tag_end, current.start_tag_end, "text"))
            )

    visit(node)
    if len(candidates) != 1:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
    return candidates[0]


def leaf_edit(node: XmlElementSpan, span: XmlTextSpan, replacement: bytes) -> ByteEdit:
    if node.self_closing:
        return ByteEdit(
            node.start_tag_end - 2,
            node.start_tag_end,
            b">" + replacement + b"</" + node.name.encode("utf-8") + b">",
        )
    return ByteEdit(span.start, span.end, replacement)
