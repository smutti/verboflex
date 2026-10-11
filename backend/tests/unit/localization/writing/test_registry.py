from __future__ import annotations

from dataclasses import replace

import pytest

from verboflex.localization.writing.core import WritebackReason, WritebackRejected

from ._support import edit, render, snapshot


def test_duplicate_canonical_selection_is_rejected() -> None:
    source = snapshot(b'<resources><string name="k">old</string></resources>')
    change = edit(source, "k", "new")
    with pytest.raises(WritebackRejected) as error:
        render(source, change, change)
    assert error.value.reason == WritebackReason.AMBIGUOUS_LOCATOR


def test_unique_sibling_in_duplicate_file_is_rejected() -> None:
    valid = snapshot(b'<resources><string name="k">old</string></resources>')
    duplicate = snapshot(
        b'<resources><string name="k">old</string>'
        b'<string name="dup">one</string><string name="dup">two</string></resources>'
    )
    with pytest.raises(WritebackRejected) as error:
        render(duplicate, edit(valid, "k", "new"))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


@pytest.mark.parametrize("field,value", [("expected_text", "stale"), ("logical_key", "other")])
def test_foreign_or_stale_selector_is_rejected(field: str, value: str) -> None:
    source = snapshot(b'<resources><string name="k">old</string></resources>')
    with pytest.raises(WritebackRejected):
        render(source, replace(edit(source, "k", "new"), **{field: value}))


def test_forged_locator_is_rejected_before_planning() -> None:
    source = snapshot(b'<resources><string name="k">old</string></resources>')
    change = edit(source, "k", "new")
    with pytest.raises(WritebackRejected):
        render(source, replace(change, locator=replace(change.locator, position=1)))


def test_xliff_document_remains_read_only() -> None:
    source = snapshot(b"not an xliff document", format="xliff")
    with pytest.raises(WritebackRejected) as error:
        render(source)
    assert error.value.reason == WritebackReason.UNSUPPORTED_FORMAT


@pytest.mark.parametrize(
    "content",
    [
        b'<!DOCTYPE resources [<!ENTITY secret "unsafe">]>'
        b'<resources><string name="k">&secret;</string></resources>',
        b'<resources><string name="k">missing end',
    ],
)
def test_malformed_or_entity_input_is_rejected_before_byte_indexing(content: bytes) -> None:
    with pytest.raises(WritebackRejected) as error:
        render(snapshot(content))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE
