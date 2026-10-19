"""Closed format dispatch with whole-file semantic and byte preservation checks."""

from __future__ import annotations

import hashlib
from dataclasses import replace

from verboflex.localization.importing.core import (
    MAX_CANONICAL_VALUES,
    CanonicalParserInput,
    CanonicalValue,
    canonical_selector_bytes,
)
from verboflex.localization.writing import android_xml, ios_strings, json, qt_ts
from verboflex.localization.writing.core import (
    RenderedFile,
    SourceFileSnapshot,
    WritebackReason,
    WritebackRejected,
    WriteEdit,
    WriteInsert,
    WriteOperation,
    apply_byte_edits,
)
from verboflex.localization.writing.parsing import inspect_writeback_snapshot


def _identity(value: CanonicalValue | WriteEdit) -> tuple[str, str, bytes]:
    return value.logical_key, value.language, canonical_selector_bytes(value.selector)


def _structure(value: CanonicalValue, *, selected: bool) -> tuple[object, ...]:
    # iOS positions/document length are derived from earlier tokens. Keep every
    # original raw key, unselected value and trivia field despite shifted offsets.
    ios_coordinates = {
        "span_start",
        "span_end",
        "equals_start",
        "equals_end",
        "semicolon_start",
        "semicolon_end",
    }
    return tuple(
        (
            node.kind,
            tuple(
                (key, field)
                for key, field in node.fields
                if not (
                    (selected and node.kind == "android_xml:cdata" and key == "value")
                    or (node.kind.startswith("ios_strings:") and key in ios_coordinates)
                    or (node.kind == "ios_strings:document" and key == "decoded_characters")
                    or (
                        selected
                        and node.kind == "ios_strings:value"
                        and key in {"raw", "escapes", "escape_style"}
                    )
                )
            ),
        )
        for node in value.structure
        if not selected
        or node.kind not in {"android_xml:text", "android_xml:tail", "qt_ts:text", "json:string"}
    )


def _render_edits(
    parser_input: CanonicalParserInput,
    edits: tuple[WriteEdit, ...],
) -> tuple[bytes, tuple[WriteEdit, ...]]:
    """Shared pure boundary for verified envelopes and the legacy local MOKO helper."""
    if type(parser_input) is not CanonicalParserInput or parser_input.format not in {
        "android_xml",
        "qt_ts",
        "json",
        "ios_strings",
    }:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_FORMAT)
    if type(edits) is not tuple or len(edits) > MAX_CANONICAL_VALUES:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    parsed = inspect_writeback_snapshot(parser_input)
    if parsed.issues:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
    originals = {_identity(value): value for value in parsed.values}
    resource_positions: dict[str, set[int]] = {}
    if parser_input.format == "android_xml":
        for occurrence in parsed.values:
            resource_positions.setdefault(occurrence.logical_key, set()).add(
                occurrence.locator.position
            )
    selected: dict[tuple[str, str, bytes], WriteEdit] = {}
    for edit in edits:
        if type(edit) is not WriteEdit:
            raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
        identity = _identity(edit)
        if identity in selected or len(resource_positions.get(edit.logical_key, ())) > 1:
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        value = originals.get(identity)
        if value is None or value.locator != edit.locator:
            raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        if value.display_text != edit.expected_text:
            raise WritebackRejected(WritebackReason.STALE_BASIS)
        if parser_input.format == "qt_ts":
            qt_ts.require_writable_value(parser_input, value)
        selected[identity] = edit
    changed = tuple(
        (value, selected[_identity(value)])
        for value in parsed.values
        if _identity(value) in selected
        and value.display_text != selected[_identity(value)].replacement_text
    )
    if not changed:
        return parser_input.content, ()
    adapter = {
        "android_xml": android_xml,
        "qt_ts": qt_ts,
        "json": json,
        "ios_strings": ios_strings,
    }[parser_input.format]
    spans = adapter.plan_edits(parser_input, changed)
    content = apply_byte_edits(parser_input.content, spans)
    reparsed = inspect_writeback_snapshot(replace(parser_input, content=content))
    if reparsed.issues or tuple(map(_identity, reparsed.values)) != tuple(
        map(_identity, parsed.values)
    ):
        raise WritebackRejected(WritebackReason.INVALID_OUTPUT)
    for before, after in zip(parsed.values, reparsed.values, strict=True):
        change = selected.get(_identity(before))
        expected = change.replacement_text if change is not None else before.display_text
        if (
            after.display_text != expected
            or _structure(before, selected=change is not None)
            != _structure(after, selected=change is not None)
            or (
                change is None
                and (before.source_text, before.translated_text)
                != (after.source_text, after.translated_text)
            )
        ):
            raise WritebackRejected(WritebackReason.INVALID_OUTPUT)
    return content, tuple(edit for _, edit in changed)


def render_file(snapshot: SourceFileSnapshot, edits: tuple[WriteOperation, ...]) -> RenderedFile:
    if type(snapshot) is not SourceFileSnapshot:
        raise WritebackRejected(WritebackReason.STALE_BASIS)
    if (
        type(edits) is not tuple
        or len(edits) > MAX_CANONICAL_VALUES
        or any(type(edit) not in (WriteEdit, WriteInsert) for edit in edits)
    ):
        raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
    replacements = tuple(edit for edit in edits if isinstance(edit, WriteEdit))
    additions = tuple(edit for edit in edits if isinstance(edit, WriteInsert))
    content, changed = _render_edits(snapshot.parser_input, replacements)
    if additions:
        from verboflex.localization.writing.insertions import render_insertions

        content = render_insertions(replace(snapshot.parser_input, content=content), additions)
    return RenderedFile(
        snapshot.authority,
        snapshot.parser_input.content,
        content,
        snapshot.authority.sha256,
        hashlib.sha256(content).hexdigest(),
        changed + additions,
        snapshot.attributes,
    )
