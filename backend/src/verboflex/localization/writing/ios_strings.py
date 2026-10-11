"""Replace canonical iOS value tokens in their verified original byte encoding."""

from __future__ import annotations

from unicodedata import category

from verboflex.localization.importing.core import CanonicalParserInput, CanonicalValue
from verboflex.localization.importing.ios_strings import (
    MAX_IOS_ESCAPES_PER_TOKEN,
    _decode_document,
)
from verboflex.localization.writing.core import (
    ByteEdit,
    ByteEditBuffer,
    WritebackReason,
    WritebackRejected,
    WriteEdit,
)

_BOMS = {"none": b"", "utf-8": b"\xef\xbb\xbf", "utf-16-le": b"\xff\xfe", "utf-16-be": b"\xfe\xff"}
_ESCAPES = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
_ESCAPE_TABLE = str.maketrans(_ESCAPES)


def encode_text(text: str, *, encoding: str) -> bytes:
    if any(category(char) == "Cc" and char not in "\n\r\t" for char in text):
        raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
    if sum(char in _ESCAPES for char in text) > MAX_IOS_ESCAPES_PER_TOKEN:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    try:
        return ('"' + text.translate(_ESCAPE_TABLE) + '"').encode(encoding)
    except UnicodeEncodeError:
        raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT) from None


def _encoded_offsets(
    source: str, content: bytes, *, encoding: str, bom: bytes, boundaries: set[int]
) -> dict[int, int]:
    """Encode disjoint segments once, proving all original bytes while mapping offsets."""
    boundaries.update((0, len(source)))
    if not content.startswith(bom) or any(
        type(boundary) is not int or not 0 <= boundary <= len(source) for boundary in boundaries
    ):
        raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
    offsets: dict[int, int] = {}
    previous = 0
    position = len(bom)
    for boundary in sorted(boundaries):
        segment = source[previous:boundary].encode(encoding)
        end = position + len(segment)
        if content[position:end] != segment:
            raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
        offsets[boundary] = end
        previous, position = boundary, end
    if position != len(content):
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
    return offsets


def plan_edits(
    parser_input: CanonicalParserInput,
    changes: tuple[tuple[CanonicalValue, WriteEdit], ...],
) -> tuple[ByteEdit, ...]:
    # The registry has already run the complete canonical lexer. Its value spans
    # are character coordinates; decoding uses that lexer's exact codec boundary.
    try:
        decoded = _decode_document(parser_input.content)
    except ValueError:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE) from None
    selected: list[tuple[int, int, WriteEdit]] = []
    boundaries: set[int] = set()
    for value, change in changes:
        nodes = [node for node in value.structure if node.kind == "ios_strings:value"]
        if len(nodes) != 1:
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        fields = dict(nodes[0].fields)
        start, end = fields.get("span_start"), fields.get("span_end")
        if (
            type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= len(decoded.source)
            or decoded.source[start:end] != fields.get("raw")
        ):
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        boundaries.update((start, end))
        selected.append((start, end, change))
    offsets = _encoded_offsets(
        decoded.source,
        parser_input.content,
        encoding=decoded.encoding,
        bom=_BOMS[decoded.bom],
        boundaries=boundaries,
    )
    edits = ByteEditBuffer()
    for start, end, change in selected:
        edits.append(
            ByteEdit(
                offsets[start],
                offsets[end],
                encode_text(change.replacement_text, encoding=decoded.encoding),
            )
        )
    return edits.freeze()
