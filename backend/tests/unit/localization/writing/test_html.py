"""Synthetic email templates prove byte-preserving edits and closed boundaries."""

from dataclasses import replace

import pytest

from verboflex.localization.html import html_path, index_html, valid_html_replacement
from verboflex.localization.importing.registry import (
    parse_canonical_mapping,
    parse_canonical_snapshot,
)
from verboflex.localization.preview.html import detect_html_layouts
from verboflex.localization.writing.core import WritebackRejected
from verboflex.services.repository_discovery import RepositorySourceFile

from ._support import edit, render, snapshot

EMAIL = (
    b'<!DOCTYPE html>\r\n<html lang="wrong"><head><title>Welcome &amp; hello</title>'
    b"<style>p { color: red; }</style></head><body><!--[if mso]>unchanged<![endif]-->"
    b'<p class="intro"> Hello <b>{{ first_name }}</b>, welcome &amp; enjoy.</p>'
    b'<a href="{{cta_url}}" style="color:blue">Continue</a></body></html>'
)


def source(content: bytes = EMAIL, path: str = "draft/mail/Welcome-EN.html"):
    return snapshot(content, format="html", path=path, layout_identity="html:draft/mail")


def test_html_round_trip_and_only_selected_text_bytes_change() -> None:
    original = source()
    parsed = parse_canonical_snapshot(original.parser_input)
    assert not parsed.issues
    assert len(parsed.values) == 5
    assert {value.language for value in parsed.values} == {"en"}
    assert render(original).content == EMAIL
    value = next(value for value in parsed.values if value.display_text == "Hello")
    changed = render(original, edit(original, value.logical_key, "Ciao <amico> & caffè"))
    assert changed.content == EMAIL.replace(b"Hello", "Ciao &lt;amico&gt; &amp; caffè".encode())
    assert index_html(changed.content)[1] == index_html(EMAIL)[1]


def test_html_multiple_edits_preserve_addresses_and_unselected_entities() -> None:
    original = source()
    parsed = parse_canonical_snapshot(original.parser_input)
    changes = tuple(
        edit(original, value.logical_key, value.display_text + "!")
        for value in parsed.values
        if "{{" not in value.display_text
    )
    changed = render(original, *changes)
    assert b"<!--[if mso]>unchanged<![endif]-->" in changed.content
    assert b'href="{{cta_url}}"' in changed.content
    assert b"<b>{{ first_name }}</b>" in changed.content


@pytest.mark.parametrize("replacement", ["", "   ", "{{name}}", "{{ first_name }} {{extra}}"])
def test_html_variable_changes_and_removed_slots_are_rejected(replacement: str) -> None:
    original = source()
    value = next(
        v
        for v in parse_canonical_snapshot(original.parser_input).values
        if v.display_text == "{{ first_name }}"
    )
    with pytest.raises(WritebackRejected):
        render(original, edit(original, value.logical_key, replacement))


@pytest.mark.parametrize(
    "content",
    [
        b"<html><p>broken</html>",
        b"<html><body></body></html>",
        b"<!DOCTYPE html [external]><html>x</html>",
        b"\xff",
    ],
)
def test_html_malformed_input_has_no_partial_output(content: bytes) -> None:
    result = parse_canonical_snapshot(source(content).parser_input)
    assert result.issues and not result.values


def test_html_filename_locale_is_authoritative_and_regional_suffix_is_unambiguous() -> None:
    assert html_path("nested/Welcome-FR-BE.html") == ("fr-BE", "nested/Welcome", "-")
    assert html_path("nested/Welcome_IT.html") == ("it", "nested/Welcome", "_")
    assert html_path("nested/Welcome.html") is None
    assert html_path("nested/Welcome-try-EN.html") == ("en", "nested/Welcome-try", "-")
    parsed = parse_canonical_snapshot(source(path="draft/mail/Welcome-FR-BE.html").parser_input)
    assert {v.language for v in parsed.values} == {"fr-BE"}
    assert all(v.translated_text is not None for v in parsed.values)


def test_html_preview_has_one_collection_for_nested_templates() -> None:
    files = tuple(
        RepositorySourceFile(path, EMAIL)
        for path in (
            "draft/mail/Welcome-EN.html",
            "draft/mail/Welcome-IT.html",
            "draft/mail/reminders/Reminder-EN.html",
        )
    )
    result = detect_html_layouts(files, repository_side="direct")
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.layout_identity == "html:draft/mail"
    assert len(candidate.keys) == 10
    assert candidate.languages == ("en", "it")


def test_html_unchanged_text_does_not_need_variable_normalization() -> None:
    assert valid_html_replacement("Hi {{ name }}", "Bonjour {{ name }}")
    assert not valid_html_replacement("Hi {{ name }}", "Bonjour {{name}}")
    original = source()
    parsed = parse_canonical_snapshot(original.parser_input)
    value = parsed.values[0]
    with pytest.raises(WritebackRejected):
        render(original, replace(edit(original, value.logical_key, "Other"), expected_text="stale"))


def test_different_language_topology_is_not_silently_aligned() -> None:
    english = source().parser_input
    target = replace(
        english,
        path="draft/mail/Welcome-IT.html",
        content=EMAIL.replace(b"<b>", b"<i>").replace(b"</b>", b"</i>"),
    )
    result = parse_canonical_mapping((english, target))
    assert result.issues and not result.values


def test_preview_removes_navigation_and_active_markup_without_touching_source() -> None:
    from verboflex.localization.html_preview import passive_html_preview

    raw = (
        '<html><head><meta http-equiv="refresh" content="0;url=https://example.test">'
        '<style>p {color:red}</style></head><body onload="alert(1)">'
        '<a href="https://example.test">Link</a><img src="https://example.test/image" alt="Image">'
        "<script>alert(1)</script><p><!--VERBOFLEX-SELECTED-TEXT--></p></body></html>"
    )
    preview = passive_html_preview(raw)
    assert "http-equiv" not in preview and "href=" not in preview and "src=" not in preview
    assert "onload" not in preview and "<script" not in preview and "alert(1)" not in preview
    assert "<a>Link</a>" in preview and "p {color:red}" in preview
    assert "<!--VERBOFLEX-SELECTED-TEXT-->" in preview
