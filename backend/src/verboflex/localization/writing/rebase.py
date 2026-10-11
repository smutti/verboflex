"""Read-only replay for checking an externally rebased submission.

This does not renew approval or authorize a repository mutation.
"""

from dataclasses import replace

from verboflex.localization.importing.core import CanonicalParserInput, canonical_selector_bytes
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.writing.core import (
    WritebackReason,
    WritebackRejected,
    WriteEdit,
    WriteInsert,
    WriteOperation,
)
from verboflex.localization.writing.insertions import render_insertions
from verboflex.localization.writing.registry import _render_edits


def replay_approved_edits(
    parser: CanonicalParserInput, operations: tuple[WriteOperation, ...]
) -> bytes:
    parsed = parse_canonical_snapshot(parser)
    if parsed.issues:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
    values = {
        (v.logical_key, v.language, canonical_selector_bytes(v.selector)): v for v in parsed.values
    }
    if len(values) != len(parsed.values):
        raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
    edits: list[WriteEdit] = []
    additions: list[WriteInsert] = []
    for operation in operations:
        value = values.get(
            (
                operation.logical_key,
                operation.language,
                canonical_selector_bytes(operation.selector),
            )
        )
        if isinstance(operation, WriteInsert):
            if value is None:
                additions.append(operation)
            elif value.display_text != operation.replacement_text:
                raise WritebackRejected(WritebackReason.STALE_BASIS)
        elif value is None:
            raise WritebackRejected(WritebackReason.SOURCE_FILE_CHANGED)
        else:
            edits.append(
                replace(operation, locator=value.locator, expected_text=value.display_text)
            )
    content, _ = _render_edits(parser, tuple(edits))
    if additions:
        content = render_insertions(replace(parser, content=content), tuple(additions))
    return content
