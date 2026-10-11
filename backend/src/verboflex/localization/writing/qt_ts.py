"""Qt translation-leaf edits over exact canonical message and variant identities."""

from __future__ import annotations

from unicodedata import category
from xml.sax.saxutils import escape

from verboflex.localization.importing.core import CanonicalParserInput, CanonicalValue
from verboflex.localization.writing.core import (
    ByteEdit,
    ByteEditBuffer,
    WritebackReason,
    WritebackRejected,
    WriteEdit,
)
from verboflex.localization.writing.xml_spans import (
    XmlElementSpan,
    editable_leaf,
    index_xml,
    leaf_edit,
)


def require_writable_value(parser_input: CanonicalParserInput, value: CanonicalValue) -> None:
    """Guard read-only source and deleted translations even for exact no-ops."""
    if parser_input.repository_side == "keys" or any(
        node.kind == "qt_ts:translation" and dict(node.fields).get("deleted") is True
        for node in value.structure
    ):
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)


def encode_text(text: str, *, cdata: bool) -> bytes:
    if any(
        (category(character) == "Cc" and character not in "\n\r\t")
        or ord(character) in (0xFFFE, 0xFFFF)
        for character in text
    ):
        raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
    if cdata:
        # XML normalizes literal CR even in CDATA; entities are literal there.
        # Refuse text requiring a split wrapper instead of changing its shape.
        if "]]>" in text or "\r" in text or "\ufeff" in text:
            raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
        return text.encode("utf-8")
    # A literal second BOM is not accepted by the canonical Qt decoder.
    return escape(text).replace("\r", "&#13;").replace("\ufeff", "&#65279;").encode("utf-8")


def _at(nodes: tuple[XmlElementSpan, ...], index: object) -> XmlElementSpan:
    if type(index) is not int or not 0 <= index < len(nodes):
        raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
    return nodes[index]


def _translation_leaf(message: XmlElementSpan, value: CanonicalValue) -> XmlElementSpan:
    translations = tuple(child for child in message.children if child.name == "translation")
    if len(translations) != 1:
        raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
    selected = translations[0]
    fields = dict(value.selector.fields)
    address = value.locator.structural_address[:5]
    if value.selector.kind == "qt_numerus" or (
        value.selector.kind == "qt_length_variant" and "form_index" in fields
    ):
        form_index = fields.get("form_index")
        selected = _at(selected.children, form_index)
        if selected.name != "numerusform" or type(form_index) is not int:
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        address += ("numerusform", form_index)
    if value.selector.kind == "qt_length_variant":
        priority = fields.get("priority")
        variants = tuple(
            child
            for child in selected.children
            if child.name == "lengthvariant"
            and dict(child.attributes).get("priority") == str(priority)
        )
        if type(priority) is not int or len(variants) != 1:
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        selected = variants[0]
        address += ("lengthvariant", priority)
    elif value.selector.kind not in {"scalar", "qt_numerus"}:
        raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
    if address != value.locator.structural_address:
        raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
    return selected


def plan_edits(
    parser_input: CanonicalParserInput,
    selections: tuple[tuple[CanonicalValue, WriteEdit], ...],
) -> tuple[ByteEdit, ...]:
    root = index_xml(parser_input.content, allow_ts_doctype=True)
    if root.name != "TS":
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
    messages: dict[tuple[str | int, ...], tuple[int, XmlElementSpan]] = {}
    contexts = (child for child in root.children if child.name == "context")
    for context_index, context in enumerate(contexts):
        children = (child for child in context.children if child.name == "message")
        for message_index, message in enumerate(children):
            address = ("TS", "context", context_index, "message", message_index)
            messages[address] = len(messages), message
    output = ByteEditBuffer()
    for value, edit in selections:
        require_writable_value(parser_input, value)
        matched = messages.get(value.locator.structural_address[:5])
        if matched is None or matched[0] != value.locator.position:
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        message = matched[1]
        identifier = dict(message.attributes).get("id")
        identity_kind = dict(value.selector.fields).get("identity_kind")
        if (
            (identity_kind == "id" and identifier != value.logical_key)
            or (
                identity_kind == "source"
                and (identifier is not None or value.logical_key != value.source_text)
            )
            or identity_kind not in {"id", "source"}
        ):
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        selected = _translation_leaf(message, value)
        leaf, span = editable_leaf(selected, allow_styles=False)
        output.append(
            leaf_edit(leaf, span, encode_text(edit.replacement_text, cdata=span.kind == "cdata"))
        )
    return output.freeze()
