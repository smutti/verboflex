"""Qt text-only write-back: exact original bytes and complete typed authority."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.writing.core import (
    SourceFileSnapshot,
    WritebackReason,
    WritebackRejected,
)

from ._support import edit, render, snapshot

FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization"
QT_WRITING = FIXTURES / "writing" / "qt"


def _source(content: bytes | None = None, **changes: object) -> SourceFileSnapshot:
    fields: dict[str, object] = {
        "format": "qt_ts",
        "path": "translations/app_it.ts",
        "layout_identity": "qt-ts:translations/app_{locale}.ts",
    }
    fields.update(changes)
    return snapshot(
        content if content is not None else (QT_WRITING / "variants.ts").read_bytes(), **fields
    )


def _document(translation: bytes = b"Old", *, attributes: bytes = b"") -> bytes:
    return (
        b"<TS version='2.1' language='it'><context><name>Main</name>"
        b"<message id='k'><source>Source &amp; text</source><translation"
        + attributes
        + b">"
        + translation
        + b"</translation></message></context></TS>"
    )


def test_scalar_source_identity_and_id_do_not_collide() -> None:
    source = _source()
    changes = (
        edit(source, "shared", "New <scalar> & 😀", identity_kind="id"),
        edit(
            source,
            "shared",
            "Changed source identity",
            identity_kind="source",
            context="Main",
            disambiguation="other",
        ),
        edit(source, "plain", "%n more items", form_index=1),
        edit(source, "short", "D.", priority=3),
        edit(source, "nested", "One selected", form_index=0, priority=7),
        edit(source, "nested", "%n selected\r\nnext line", form_index=1, priority=31),
    )
    expected = (QT_WRITING / "variants.expected.ts").read_bytes()
    result = render(source, *changes)
    assert result.content == expected
    assert render(source, *reversed(changes)).content == expected
    assert result.original_bytes == source.parser_input.content
    assert set(result.changed_edits) == set(changes)


def test_nested_numerus_priority_edits_exact_leaf() -> None:
    source = _source()
    changes = (
        edit(source, "nested", "X", form_index=0, priority=31),
        edit(source, "nested", "Much longer leaf", form_index=1, priority=7),
    )
    assert render(source, *changes).content == source.parser_input.content.replace(
        b">First long<", b">X<"
    ).replace(b">Second short<", b">Much longer leaf<")


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
def test_standard_doctype_and_crlf_are_unchanged(bom: bytes) -> None:
    content = bom + (QT_WRITING / "variants.ts").read_bytes().replace(b"\n", b"\r\n")
    source = _source(content)
    assert render(source, edit(source, "short", "Device", priority=20)).content == content.replace(
        b">Long<", b">Device<"
    )


def test_translation_status_is_preserved() -> None:
    source = _source(
        (FIXTURES / "qt" / "valid_structured.ts").read_bytes(),
        path="translations/app_it-IT.ts",
    )
    result = render(source, edit(source, "checkout.pay", "Paga adesso", identity_kind="id"))
    assert result.content == source.parser_input.content.replace(
        b"Paga &lt;ora&gt;", b"Paga adesso"
    )
    assert b'type="unfinished"' in result.content
    assert b'type="obsolete"' in result.content
    assert b'type="vanished"' in result.content


@pytest.mark.parametrize("status", ["obsolete", "vanished"])
@pytest.mark.parametrize("replacement", ["Old", "New"])
def test_deleted_translation_is_rejected_even_for_noop(status: str, replacement: str) -> None:
    source = _source(_document(attributes=f" type='{status}'".encode()))
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "k", replacement))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


@pytest.mark.parametrize("replacement", ["Source & text", "New"])
def test_keys_side_never_writes_source_or_translation(replacement: str) -> None:
    source = _source(_document(), repository_side="keys")
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "k", replacement))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


@pytest.mark.parametrize(
    "content",
    [
        _document(b"Old<!-- note -->"),
        _document(b"Old<byte value='x20'/>"),
        _document(b"Old<?pi keep?>"),
        b"<!-- root comment -->" + _document(),
    ],
)
def test_xml_comment_or_byte_child_is_explicitly_unsupported(content: bytes) -> None:
    with pytest.raises(WritebackRejected) as error:
        render(_source(content))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


@pytest.mark.parametrize(
    ("before", "text", "after"),
    [
        (b"<translation />", "<new> & safe", b"<translation >&lt;new&gt; &amp; safe</translation>"),
        (b"<translation></translation>", "", b"<translation></translation>"),
        (
            b"<translation><![CDATA[old]]></translation>",
            "<new> & safe",
            b"<translation><![CDATA[<new> & safe]]></translation>",
        ),
        (
            b"<translation><![CDATA[]]></translation>",
            "filled",
            b"<translation><![CDATA[filled]]></translation>",
        ),
    ],
)
def test_qt_self_closing_and_cdata(before: bytes, text: str, after: bytes) -> None:
    content = _document().replace(b"<translation>Old</translation>", before)
    source = _source(content)
    assert render(source, edit(source, "k", text)).content == content.replace(before, after)


@pytest.mark.parametrize("replacement", ["]]>", "line\rreturn", "\ufeff"])
def test_cdata_cannot_encode_delimiter_or_carriage_return_without_structure_change(
    replacement: str,
) -> None:
    source = _source(_document(b"<![CDATA[Old]]>"))
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "k", replacement))
    assert error.value.reason == WritebackReason.INVALID_REPLACEMENT


def test_mixed_cdata_is_unsupported_for_changes_but_noop_is_exact() -> None:
    source = _source(_document(b"Old<![CDATA[ mixed]]>"))
    assert render(source, edit(source, "k", "Old mixed")).content is source.parser_input.content
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "k", "Flattened"))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


@pytest.mark.parametrize(
    "doctype",
    [
        b"<!DOCTYPE TS SYSTEM 'https://invalid.example/secret'>",
        b"<!DOCTYPE TS [<!ENTITY hidden 'secret'>]>",
        b"<!DOCTYPE TS><!DOCTYPE TS>",
    ],
)
def test_unsafe_doctypes_are_rejected_without_source_in_error(doctype: bytes) -> None:
    with pytest.raises(WritebackRejected) as error:
        render(_source(doctype + _document()))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE
    assert "secret" not in str(error.value)
    assert "invalid.example" not in str(error.value)


@pytest.mark.parametrize("text", ["a\x00b", "\x7f", "\x85", "\ufffe", "\uffff"])
def test_qt_invalid_replacement_characters_are_closed_failures(text: str) -> None:
    source = _source(_document())
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "k", text))
    assert error.value.reason == WritebackReason.INVALID_REPLACEMENT


def test_qt_text_byte_order_mark_is_encoded_as_entity() -> None:
    source = _source(_document())
    result = render(source, edit(source, "k", "\ufeff"))
    assert result.content == source.parser_input.content.replace(b">Old<", b">&#65279;<")
    assert (
        parse_canonical_snapshot(replace(source.parser_input, content=result.content))
        .values[0]
        .display_text
        == "\ufeff"
    )


def test_stale_locator_cannot_select_another_message() -> None:
    source = _source()
    wanted = edit(source, "shared", "New", identity_kind="id")
    wrong = replace(wanted, locator=replace(wanted.locator, position=1))
    with pytest.raises(WritebackRejected) as error:
        render(source, wrong)
    assert error.value.reason == WritebackReason.AMBIGUOUS_LOCATOR


def test_duplicate_file_refuses_valid_sibling() -> None:
    source = _source(_document())
    wanted = edit(source, "k", "New")
    content = source.parser_input.content.replace(
        b"</context>",
        b"<message id='k'><source>Duplicate</source>"
        b"<translation>X</translation></message></context>",
    )
    with pytest.raises(WritebackRejected) as error:
        render(_source(content), wanted)
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


@settings(max_examples=70, deadline=None)
@given(text=st.text(alphabet="abc XYZé漢😀&<>\\\"'\n\t\r", max_size=80))
def test_qt_escaping_preserves_source_metadata_and_unselected_values(text: str) -> None:
    source = _source()
    output = render(source, edit(source, "short", text, priority=3)).content
    before = parse_canonical_snapshot(source.parser_input)
    after = parse_canonical_snapshot(replace(source.parser_input, content=output))
    assert not after.issues
    for original, modified in zip(before.values, after.values, strict=True):
        assert original.source_text == modified.source_text
        if original.logical_key == "short" and dict(original.selector.fields)["priority"] == 3:
            assert modified.display_text == text
            assert tuple(n for n in original.structure if n.kind != "qt_ts:text") == tuple(
                n for n in modified.structure if n.kind != "qt_ts:text"
            )
        else:
            assert original == modified
