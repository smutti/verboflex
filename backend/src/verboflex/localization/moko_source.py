"""Lossless MOKO source edit boundary."""

from xml.sax.saxutils import escape

from verboflex.localization.importing.core import CanonicalParserInput, CanonicalValue
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.moko_layout import moko_layout


def replace_moko_scalar_text(
    parser_input: CanonicalParserInput,
    value: CanonicalValue,
    replacement_text: str,
) -> bytes:
    """Replace one confirmed scalar body while retaining every byte outside it."""
    layout = moko_layout(parser_input.path) if type(parser_input) is CanonicalParserInput else None
    if (
        type(parser_input) is not CanonicalParserInput
        or type(value) is not CanonicalValue
        or type(replacement_text) is not str
        or layout is None
        or layout[0] != parser_input.layout_identity
        or value.selector.kind != "scalar"
        or value.locator.path != parser_input.path
        or value.locator.repository_side != parser_input.repository_side
        or value.locator.structural_address != ("resources", "string", value.locator.position)
    ):
        raise ValueError("MOKO source edit rejected")
    parsed = parse_canonical_snapshot(parser_input)
    if parsed.issues or value not in parsed.values:
        raise ValueError("MOKO source edit rejected")
    # Preserve the legacy input grammar while routing every edit through the
    # shared full-file preservation proof. Markup is never replaced wholesale.
    _encode_moko_display_text(replacement_text)
    from verboflex.localization.writing.core import WritebackRejected, WriteEdit
    from verboflex.localization.writing.registry import _render_edits

    try:
        content, _ = _render_edits(
            parser_input,
            (
                WriteEdit(
                    value.logical_key,
                    value.language,
                    value.selector,
                    value.locator,
                    value.display_text,
                    replacement_text,
                ),
            ),
        )
    except WritebackRejected:
        raise ValueError("MOKO source edit rejected") from None
    return content


def _encode_moko_display_text(value: str) -> bytes:
    if value.endswith("\\") or "\\u" in value:
        raise ValueError("MOKO source edit rejected")
    source_text = value.replace("\\", "\\\\")
    return escape(source_text).encode("utf-8")


def _scalar_body_range(content: bytes, *, position: int) -> tuple[int, int, bool]:
    from verboflex.localization.writing.core import WritebackRejected
    from verboflex.localization.writing.xml_spans import index_xml

    try:
        root = index_xml(content)
        if type(position) is not int or not 0 <= position < len(root.children):
            raise ValueError("MOKO source edit rejected")
        node = root.children[position]
        if root.name != "resources" or node.name != "string":
            raise ValueError("MOKO source edit rejected")
        if node.self_closing:
            return node.start_tag_end - 2, node.start_tag_end, True
        return node.start_tag_end, node.end_tag_start, False
    except WritebackRejected:
        raise ValueError("MOKO source edit rejected") from None


def _tag_end(content: bytes, start: int) -> int:
    from verboflex.localization.writing.core import WritebackRejected
    from verboflex.localization.writing.xml_spans import tag_end

    try:
        return tag_end(content, start)
    except WritebackRejected:
        raise ValueError("MOKO source edit rejected") from None
