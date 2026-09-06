"""Approved MOKO-only escape and opaque-layout preservation contract."""

from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verboflex.localization import moko_source
from verboflex.localization.duplicate_diagnostics import inspect_duplicate_keys
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.moko_source import replace_moko_scalar_text

FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization" / "moko_xml"


def moko_input(content: bytes, **changes: object) -> CanonicalParserInput:
    return replace(
        CanonicalParserInput(
            format="android_xml",
            repository_side="direct",
            path="shared/moko-resources/base/strings.xml",
            content=content,
            layout_identity="shared/moko-resources",
            layout_version=1,
            base_language="en",
        ),
        **changes,
    )


def test_moko_preserves_unknown_escape_but_decodes_known_escape() -> None:
    source = b'<resources><string name="key">Known \\n literal \\z</string></resources>'
    result = parse_canonical_snapshot(moko_input(source))
    assert result.issues == ()
    assert result.values[0].display_text == "Known \n literal \\z"
    text_node = result.values[0].structure[-1]
    assert text_node.fields == (("value", "Known \\n literal \\z"),)


def test_same_unknown_escape_remains_rejected_for_generic_android_xml() -> None:
    source = b'<resources><string name="key">literal \\z</string></resources>'
    result = parse_canonical_snapshot(
        moko_input(
            source,
            path="app/src/main/res/values/strings.xml",
            layout_identity="app/src/main/res",
        )
    )
    assert result.values == ()
    assert tuple(issue.code for issue in result.issues) == ("unsupported_structure",)


@pytest.mark.parametrize(
    "body",
    [b"bad \\u12", b"bad \\uZZZZ", b"terminal \\"],
)
def test_moko_rejects_ambiguous_unicode_and_terminal_backslash(body: bytes) -> None:
    result = parse_canonical_snapshot(
        moko_input(b'<resources><string name="key">' + body + b"</string></resources>")
    )
    assert result.values == ()
    assert tuple(issue.code for issue in result.issues) == ("unsupported_structure",)


def test_moko_opaque_direct_text_creates_no_key_and_keeps_real_positions() -> None:
    result = parse_canonical_snapshot(
        moko_input((FIXTURES / "source_preservation.xml").read_bytes())
    )
    assert result.issues == ()
    assert [(value.logical_key, value.locator.position) for value in result.values] == [
        ("first", 0),
        ("second", 1),
    ]
    assert all("layout-" not in value.display_text for value in result.values)


def test_moko_minimal_scalar_edit_preserves_every_byte_outside_selected_body() -> None:
    source = (FIXTURES / "source_preservation.xml").read_bytes()
    parser_input = moko_input(source)
    parsed = parse_canonical_snapshot(parser_input)
    assert parsed.issues == ()
    updated = replace_moko_scalar_text(parser_input, parsed.values[0], "Changed & safe")
    before, old_and_after = source.split(b"Known \\n literal \\z", 1)
    _, after = old_and_after.split(b"</string>", 1)
    assert updated == before + b"Changed &amp; safe</string>" + after
    assert b"layout-prefix" in updated
    assert b"layout-between" in updated
    assert b"Caf\xc3\xa9 &amp; tea" in updated


def test_moko_edit_supports_self_closing_scalar_and_rejects_forged_locator() -> None:
    parser_input = moko_input(
        b'<resources>opaque<string name="first" \n />'
        b'<string name="second">safe</string></resources>'
    )
    parsed = parse_canonical_snapshot(parser_input)
    assert parsed.issues == ()
    updated = replace_moko_scalar_text(parser_input, parsed.values[0], "<new> & value")
    assert updated == (
        b'<resources>opaque<string name="first" \n >&lt;new&gt; &amp; value</string>'
        b'<string name="second">safe</string></resources>'
    )
    forged = replace(
        parsed.values[0],
        locator=replace(parsed.values[0].locator, position=1),
    )
    with pytest.raises(ValueError, match="MOKO source edit rejected"):
        replace_moko_scalar_text(parser_input, forged, "wrong target")
    forged_text = replace(parsed.values[0], display_text="not the parsed value")
    with pytest.raises(ValueError, match="MOKO source edit rejected"):
        replace_moko_scalar_text(parser_input, forged_text, "wrong authority")


def test_moko_byte_locator_fails_closed_for_malformed_or_missing_target() -> None:
    with pytest.raises(ValueError, match="MOKO source edit rejected"):
        moko_source._scalar_body_range(b"<resources>", position=0)
    with pytest.raises(ValueError, match="MOKO source edit rejected"):
        moko_source._scalar_body_range(b"<resources></resources>", position=0)
    with pytest.raises(ValueError, match="MOKO source edit rejected"):
        moko_source._tag_end(b'<string name="unterminated"', 0)


@pytest.mark.parametrize("replacement", ["terminal \\", "bad \\u12", "bad\x00control"])
def test_moko_edit_rejects_replacement_that_cannot_round_trip(replacement: str) -> None:
    parser_input = moko_input(b'<resources><string name="key">old</string></resources>')
    value = parse_canonical_snapshot(parser_input).values[0]
    with pytest.raises(ValueError, match="MOKO source edit rejected"):
        replace_moko_scalar_text(parser_input, value, replacement)


@settings(max_examples=80, deadline=None)
@given(
    prefix=st.text(alphabet="abc XYZ09é漢", max_size=24),
    unknown=st.sampled_from(("z", "q", "%", "!")),
    suffix=st.text(alphabet="def UVW18é漢", max_size=24),
    replacement=st.text(alphabet="abc XYZ09&<>é漢\\z", max_size=32).filter(
        lambda value: not value.endswith("\\") and "\\u" not in value
    ),
)
def test_moko_literal_escape_and_edit_round_trip_property(
    prefix: str,
    unknown: str,
    suffix: str,
    replacement: str,
) -> None:
    raw = f"{prefix}\\{unknown}{suffix}"
    opening = b'<resources>opaque<string name="key">'
    closing = b"</string>retained</resources>"
    parser_input = moko_input(opening + raw.encode() + closing)
    parsed = parse_canonical_snapshot(parser_input)
    assert parsed.issues == ()
    assert parsed.values[0].display_text == raw
    updated = replace_moko_scalar_text(parser_input, parsed.values[0], replacement)
    assert updated.startswith(opening)
    assert updated.endswith(closing)
    reparsed = parse_canonical_snapshot(replace(parser_input, content=updated))
    assert reparsed.issues == ()
    assert reparsed.values[0].display_text == replacement


def test_moko_diagnostics_are_complete_with_preserved_shapes_and_duplicates() -> None:
    report = inspect_duplicate_keys(
        (
            moko_input(
                b"<resources>opaque"
                b'<string name="same">literal \\z</string>between'
                b'<string name="same">other</string>tail</resources>'
            ),
        )
    )
    assert report.complete
    assert report.issue_codes == ()
    assert len(report.groups) == 1
    assert report.repeated_occurrences == 1
    assert [item.position for item in report.groups[0].occurrences] == [0, 1]


@pytest.mark.parametrize(
    "content",
    [
        b'<resources><color name="x">red</color></resources>',
        b'<resources><string name="x"><em>bad</em></string></resources>',
        b'<!DOCTYPE resources><resources><string name="x">bad</string></resources>',
    ],
)
def test_moko_preservation_does_not_relax_unsupported_structure(content: bytes) -> None:
    result = parse_canonical_snapshot(moko_input(content))
    assert result.values == ()
    assert result.issues[0].code in {"malformed_file", "unsupported_structure"}
