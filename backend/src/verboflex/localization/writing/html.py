"""Replace only verified UTF-8 text spans, preserving all HTML bytes around them."""

from html import escape

from verboflex.localization.html import index_html, valid_html_replacement
from verboflex.localization.importing.core import CanonicalParserInput, CanonicalValue
from verboflex.localization.writing.core import (
    ByteEdit,
    WritebackReason,
    WritebackRejected,
    WriteEdit,
)


def plan_edits(
    parser_input: CanonicalParserInput,
    changes: tuple[tuple[CanonicalValue, WriteEdit], ...],
) -> tuple[ByteEdit, ...]:
    fragments, _ = index_html(parser_input.content)
    by_address = {fragment.address: fragment for fragment in fragments}
    edits = []
    for value, edit in changes:
        fragment = by_address[str(value.locator.structural_address[0])]
        if not valid_html_replacement(fragment.text, edit.replacement_text):
            raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
        try:
            replacement = escape(edit.replacement_text, quote=False).encode("utf-8")
        except UnicodeError:
            raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT) from None
        edits.append(ByteEdit(fragment.start, fragment.end, replacement))
    return tuple(edits)
