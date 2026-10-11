"""Android/MOKO byte edits over exact typed scalar, quantity and array selectors."""

from __future__ import annotations

from xml.sax.saxutils import escape

from verboflex.localization.importing.core import CanonicalParserInput, CanonicalValue
from verboflex.localization.moko_layout import moko_layout
from verboflex.localization.writing.core import (
    ByteEdit,
    ByteEditBuffer,
    WritebackReason,
    WritebackRejected,
    WriteEdit,
)
from verboflex.localization.writing.xml_spans import editable_leaf, index_xml, leaf_edit


def encode_text(text: str, *, cdata: bool, moko: bool) -> bytes:
    if any(
        ord(char) < 32 and char not in "\n\r\t" or ord(char) in (0xFFFE, 0xFFFF) for char in text
    ):
        raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
    escapes = {"\\": "\\\\", "\n": "\\n", "\t": "\\t", "\r": "\\u000d", '"': '\\"', "'": "\\'"}
    encoded: list[str] = []
    for index, character in enumerate(text):
        if (
            character == " "
            and not moko
            and (
                index == 0
                or index == len(text) - 1
                or text[index - 1 : index] == " "
                or text[index + 1 : index + 2] == " "
            )
        ):
            encoded.append("\\u0020")
        elif index == 0 and character in "@?":
            encoded.append("\\" + character)
        else:
            encoded.append(escapes.get(character, character))
    raw = "".join(encoded)
    if cdata and "]]>" in raw:
        raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
    return (raw if cdata else escape(raw)).encode("utf-8")


def plan_edits(
    parser_input: CanonicalParserInput,
    selections: tuple[tuple[CanonicalValue, WriteEdit], ...],
) -> tuple[ByteEdit, ...]:
    root = index_xml(parser_input.content)
    layout = moko_layout(parser_input.path)
    moko = layout is not None and layout[0] == parser_input.layout_identity
    output = ByteEditBuffer()
    for value, edit in selections:
        address = value.locator.structural_address
        position = value.locator.position
        if root.name != "resources" or position >= len(root.children):
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        resource = root.children[position]
        if dict(resource.attributes).get("name") != value.logical_key:
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        if value.selector.kind == "scalar":
            if resource.name != "string" or address != ("resources", "string", position):
                raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
            selected = resource
        else:
            if len(address) != 5 or type(address[4]) is not int:
                raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
            item = address[4]
            if item >= len(resource.children):
                raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
            selected = resource.children[item]
            fields = dict(value.selector.fields)
            if (
                selected.name != "item"
                or (
                    value.selector.kind == "android_quantity"
                    and (
                        resource.name != "plurals"
                        or dict(selected.attributes).get("quantity") != fields.get("quantity")
                    )
                )
                or (
                    value.selector.kind == "android_array_item"
                    and (resource.name != "string-array" or fields.get("index") != item)
                )
                or value.selector.kind not in {"android_quantity", "android_array_item"}
            ):
                raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        leaf, span = editable_leaf(selected, allow_styles=True)
        output.append(
            leaf_edit(
                leaf,
                span,
                encode_text(edit.replacement_text, cdata=span.kind == "cdata", moko=moko),
            )
        )
    return output.freeze()
