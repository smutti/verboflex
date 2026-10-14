"""Apply approved MOKO edits to a working file without overwriting unrelated work."""

from dataclasses import replace

from verboflex.localization.moko_layout import moko_layout
from verboflex.localization.writing.core import (
    SourceFileSnapshot,
    WritebackReason,
    WritebackRejected,
    WriteEdit,
    WriteOperation,
)
from verboflex.localization.writing.parsing import inspect_writeback_snapshot
from verboflex.localization.writing.registry import _identity, _render_edits, _structure


def overlay_approved_moko(
    snapshot: SourceFileSnapshot,
    current: bytes,
    operations: tuple[WriteOperation, ...],
    previous: tuple[WriteOperation, ...],
) -> bytes:
    """Rebind unique locations only while their approved text/structure still match.

    The caller first validates the frozen operations against the original import
    and, after the first commit, requires the last verified working-file digest.
    This is deliberately narrower than replaying edits on an arbitrary Git rebase.
    """
    parser = snapshot.parser_input
    if (
        parser.repository_side != "translations"
        or parser.format != "android_xml"
        or moko_layout(parser.path) is None
        or any(not isinstance(op, WriteEdit) for op in (*operations, *previous))
    ):
        raise WritebackRejected(WritebackReason.SOURCE_FILE_CHANGED)
    original = inspect_writeback_snapshot(parser)
    working = inspect_writeback_snapshot(replace(parser, content=current))
    if original.issues or working.issues:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
    originals = {_identity(v): v for v in original.values}
    values = {_identity(v): v for v in working.values}
    prior = {_identity(op): op for op in previous if isinstance(op, WriteEdit)}
    edits = []
    for operation in operations:
        assert isinstance(operation, WriteEdit)
        identity = _identity(operation)
        old, value = originals.get(identity), values.get(identity)
        expected = (
            prior[identity].replacement_text if identity in prior else operation.expected_text
        )
        if (
            old is None
            or value is None
            or value.display_text != expected
            or _structure(old, selected=True) != _structure(value, selected=True)
        ):
            raise WritebackRejected(WritebackReason.SOURCE_FILE_CHANGED)
        edits.append(replace(operation, locator=value.locator, expected_text=expected))
    # The renderer rejects duplicated resource names and verifies every occurrence
    # after splicing, including those belonging to unrelated products.
    return _render_edits(replace(parser, content=current), tuple(edits))[0]
