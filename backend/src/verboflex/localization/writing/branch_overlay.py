"""Apply just the newly approved MOKO values to a verified working file."""

from dataclasses import replace

from verboflex.localization.moko_layout import moko_layout
from verboflex.localization.writing.core import (
    SourceFileSnapshot,
    WritebackReason,
    WritebackRejected,
    WriteEdit,
    WriteInsert,
    WriteOperation,
)
from verboflex.localization.writing.insertions import render_insertions
from verboflex.localization.writing.parsing import inspect_writeback_snapshot
from verboflex.localization.writing.registry import _identity, _render_edits, _structure


def overlay_approved_moko(
    snapshot: SourceFileSnapshot,
    current: bytes,
    operations: tuple[WriteOperation, ...],
    previous: tuple[WriteOperation, ...],
) -> bytes:
    """Rebind an approval to unique, structurally equivalent working-file entries.

    The caller validates the operations on the frozen import first. A matching
    replacement is a no-op. An insertion may only add a missing resource, or
    recognize exactly the resource the original insertion would have produced.
    """
    parser = snapshot.parser_input
    if (
        parser.repository_side != "translations"
        or moko_layout(parser.path) is None
        or (parser.format != "android_xml")
    ):
        raise WritebackRejected(WritebackReason.SOURCE_FILE_CHANGED)
    additions = tuple(op for op in operations if isinstance(op, WriteInsert))
    reference = (
        replace(parser, content=render_insertions(parser, additions)) if additions else parser
    )
    original = inspect_writeback_snapshot(reference)
    working_input = replace(parser, content=current)
    working = inspect_writeback_snapshot(working_input)
    if original.issues or working.issues:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
    originals = {_identity(v): v for v in original.values}
    values = {_identity(v): v for v in working.values}
    positions: dict[str, set[int]] = {}
    for v in working.values:
        positions.setdefault(v.logical_key, set()).add(v.locator.position)
    prior = {_identity(op): op.replacement_text for op in previous}
    edits = []
    missing = []
    for op in operations:
        identity = _identity(op)
        old, value = originals.get(identity), values.get(identity)
        if len(positions.get(op.logical_key, ())) > 1:
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        if isinstance(op, WriteInsert) and value is None:
            if identity in prior:
                raise WritebackRejected(WritebackReason.SOURCE_FILE_CHANGED)
            missing.append(op)
            continue
        if (
            old is None
            or value is None
            or _structure(old, selected=True) != _structure(value, selected=True)
        ):
            raise WritebackRejected(WritebackReason.SOURCE_FILE_CHANGED)
        if value.display_text == op.replacement_text:
            continue
        expected = prior.get(identity, op.expected_text)
        if not isinstance(op, WriteEdit) or value.display_text != expected:
            raise WritebackRejected(WritebackReason.SOURCE_FILE_CHANGED)
        edits.append(replace(op, locator=value.locator, expected_text=expected))
    content = _render_edits(working_input, tuple(edits))[0] if edits else current
    if missing:
        content = render_insertions(replace(working_input, content=content), tuple(missing))
    return content
