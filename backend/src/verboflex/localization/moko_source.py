"""Lossless MOKO source edit boundary."""

from xml.parsers import expat
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
    replacement = _encode_moko_display_text(replacement_text)
    start, end, self_closing = _scalar_body_range(
        parser_input.content, position=value.locator.position
    )
    if self_closing:
        replacement = b">" + replacement + b"</string>"
    updated = parser_input.content[:start] + replacement + parser_input.content[end:]
    reparsed = parse_canonical_snapshot(
        CanonicalParserInput(
            format=parser_input.format,
            repository_side=parser_input.repository_side,
            path=parser_input.path,
            content=updated,
            layout_identity=parser_input.layout_identity,
            layout_version=parser_input.layout_version,
            base_language=parser_input.base_language,
        )
    )
    if reparsed.issues or not any(
        item.locator == value.locator and item.display_text == replacement_text
        for item in reparsed.values
    ):
        raise ValueError("MOKO source edit rejected")
    return updated


def _encode_moko_display_text(value: str) -> bytes:
    if value.endswith("\\") or "\\u" in value:
        raise ValueError("MOKO source edit rejected")
    source_text = value.replace("\\", "\\\\")
    return escape(source_text).encode("utf-8")


def _scalar_body_range(content: bytes, *, position: int) -> tuple[int, int, bool]:
    parser = expat.ParserCreate()
    depth = 0
    resource_position = 0
    selected: tuple[int, int, bool] | None = None

    def start_element(name: str, _attributes: dict[str, str]) -> None:
        nonlocal depth, resource_position, selected
        if depth == 1:
            current = resource_position
            resource_position += 1
            if name == "string" and current == position:
                tag_start = parser.CurrentByteIndex
                tag_end = _tag_end(content, tag_start)
                slash = tag_end - 2
                if slash >= tag_start and content[slash] == ord("/"):
                    selected = (slash, tag_end, True)
                else:
                    selected = (tag_end, -1, False)
        depth += 1

    def end_element(name: str) -> None:
        nonlocal depth, selected
        depth -= 1
        if (
            depth == 1
            and name == "string"
            and selected is not None
            and not selected[2]
            and selected[1] == -1
        ):
            selected = (selected[0], parser.CurrentByteIndex, False)

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    try:
        parser.Parse(content, True)
    except expat.ExpatError as error:
        raise ValueError("MOKO source edit rejected") from error
    if selected is None or selected[1] < selected[0]:
        raise ValueError("MOKO source edit rejected")
    return selected


def _tag_end(content: bytes, start: int) -> int:
    quote: int | None = None
    for index in range(start + 1, len(content)):
        character = content[index]
        if quote is None and character in {ord("'"), ord('"')}:
            quote = character
        elif quote == character:
            quote = None
        elif quote is None and character == ord(">"):
            return index + 1
    raise ValueError("MOKO source edit rejected")
