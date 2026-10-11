"""Golden byte edits for Android/MOKO leaves and explicit unsafe-shape refusals."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.moko_source import replace_moko_scalar_text
from verboflex.localization.writing import android_xml
from verboflex.localization.writing.core import WritebackReason, WritebackRejected

from ._support import edit, render, snapshot

FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization"


def test_structured_golden_preserves_every_unselected_byte() -> None:
    content = (FIXTURES / "android" / "valid_structured.xml").read_bytes()
    source = snapshot(content)
    changes = (
        edit(source, "files", "%d new files", quantity="other"),
        edit(source, "steps", "Last", index=0),
        edit(source, "escaped", "Short"),
    )
    expected = (FIXTURES / "writing" / "android" / "structured.expected.xml").read_bytes()
    result = render(source, *changes)
    assert result.content == expected
    assert render(source, *reversed(changes)).content == expected
    assert b"<!-- translator note -->" in result.content
    assert result.original_bytes == content


def test_mixed_markup_is_rejected_without_erasing_structure() -> None:
    source = snapshot(
        b'<resources><string name="k">Hello <b>bold</b><!--keep--> tail</string></resources>'
    )
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "k", "Flattened"))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


def test_noop_mixed_markup_preserves_bytes() -> None:
    source = snapshot(
        b'<resources><string name="k">Hello <b>bold</b><!--keep--> tail</string></resources>'
    )
    result = render(source, edit(source, "k", "Hello bold tail"))
    assert result.content is source.parser_input.content
    assert result.changed_edits == ()


def test_single_styled_leaf_retains_tags_and_comment() -> None:
    source = snapshot(
        b'<resources><string name="k"><!--note--><b><i>Old</i></b></string></resources>'
    )
    assert render(source, edit(source, "k", "New & safe")).content == (
        b'<resources><string name="k"><!--note--><b><i>New &amp; safe</i></b></string></resources>'
    )


def test_empty_comment_only_value_retains_comment_when_filled() -> None:
    source = snapshot(b'<resources><string name="k"><!--keep--></string></resources>')
    assert render(source, edit(source, "k", "New")).content == (
        b'<resources><string name="k">New<!--keep--></string></resources>'
    )


def test_protected_placeholder_cannot_be_reassigned() -> None:
    source = snapshot(
        b'<resources xmlns:x="urn:oasis:names:tc:xliff:document:1.2">'
        b'<string name="k"><x:g id="n">%d</x:g></string></resources>'
    )
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "k", "different"))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


def test_cdata_wrapper_preserved() -> None:
    source = snapshot(b'<resources><string name="k"><![CDATA[old]]></string></resources>')
    assert render(source, edit(source, "k", "<new> & safe")).content == (
        b'<resources><string name="k"><![CDATA[<new> & safe]]></string></resources>'
    )
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "k", "]]>"))
    assert error.value.reason == WritebackReason.INVALID_REPLACEMENT


def test_self_closing_expansion_is_local() -> None:
    content = b'\xef\xbb\xbf<resources>\r\n<string name="k" />\r\n</resources>'
    source = snapshot(content)
    assert render(source, edit(source, "k", "new")).content == content.replace(
        b'name="k" />', b'name="k" >new</string>'
    )


def test_moko_opaque_trivia_is_preserved() -> None:
    content = (FIXTURES / "moko_xml" / "source_preservation.xml").read_bytes()
    source = snapshot(
        content,
        path="shared/moko-resources/base/strings.xml",
        layout_identity="shared/moko-resources",
    )
    expected = content.replace(b"Known \\n literal \\z", b"Changed &amp; safe")
    assert render(source, edit(source, "first", "Changed & safe")).content == expected


def test_existing_moko_entrypoint_rejects_markup_loss() -> None:
    source = snapshot(
        b'<resources><string name="k">Hello <b>world</b><!--keep--></string></resources>',
        path="shared/moko-resources/base/strings.xml",
        layout_identity="shared/moko-resources",
    )
    value = parse_canonical_snapshot(source.parser_input).values[0]
    with pytest.raises(ValueError, match="MOKO source edit rejected"):
        replace_moko_scalar_text(source.parser_input, value, "Flattened")


@pytest.mark.parametrize("text", ["a\x00b", "\ufffe", "\uffff"])
def test_invalid_xml_characters_are_explicitly_rejected(text: str) -> None:
    source = snapshot(b'<resources><string name="k">old</string></resources>')
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "k", text))
    assert error.value.reason == WritebackReason.INVALID_REPLACEMENT


@settings(max_examples=70, deadline=None)
@given(text=st.text(alphabet="abc XYZé漢😀&<>\\\"'@?\n\t\r", max_size=80))
def test_android_text_escaping_round_trips_without_changing_siblings(text: str) -> None:
    source = snapshot(
        b'<resources><string name="k">old</string><string name="other">Keep</string></resources>'
    )
    output = render(source, edit(source, "k", text)).content
    parsed = parse_canonical_snapshot(replace(source.parser_input, content=output))
    assert not parsed.issues
    assert {v.logical_key: v.display_text for v in parsed.values} == {"k": text, "other": "Keep"}
    assert output.endswith(b'<string name="other">Keep</string></resources>')


def test_encoded_replacement_budget_stops_before_accumulating_all_edits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = (
        b"<resources>"
        + b"".join(f'<string name="k{index}">x</string>'.encode() for index in range(64))
        + b"</resources>"
    )
    source = snapshot(content)
    changes = tuple(edit(source, f"k{index}", "x" * 32768) for index in range(64))
    encoded_count = 0
    original = android_xml.encode_text

    def count(text: str, *, cdata: bool, moko: bool) -> bytes:
        nonlocal encoded_count
        encoded_count += 1
        return original(text, cdata=cdata, moko=moko)

    monkeypatch.setattr(android_xml, "encode_text", count)
    with pytest.raises(WritebackRejected) as error:
        render(source, *changes)
    assert error.value.reason == WritebackReason.LIMIT_EXCEEDED
    assert encoded_count <= 33


def test_growth_can_be_offset_by_later_shrink_without_false_limit() -> None:
    content = (
        b"<resources>"
        + b"".join(
            f'<string name="k{index:02d}">{"x" * (32768 if index else 0)}</string>'.encode()
            for index in range(32)
        )
        + b"</resources>"
    )
    source = snapshot(content)
    assert len(content) + 32768 > 1_048_576
    result = render(source, edit(source, "k00", "x" * 32768), edit(source, "k31", ""))
    assert len(result.content) == len(content)
    assert result.content == content.replace(
        b'<string name="k00"></string>', b'<string name="k00">' + b"x" * 32768 + b"</string>"
    ).replace(b'<string name="k31">' + b"x" * 32768 + b"</string>", b'<string name="k31"></string>')
