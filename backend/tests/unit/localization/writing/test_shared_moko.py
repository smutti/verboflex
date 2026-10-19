"""Shared code-key catalogs may contain unrelated, quarantined duplicates."""

from dataclasses import replace

import pytest

from verboflex.integrations.bitbucket.client import BitbucketSourceMetadata
from verboflex.localization.importing.android_xml import inspect_android_xml
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.writing.core import WritebackReason, WritebackRejected, WriteEdit
from verboflex.localization.writing.registry import render_file
from verboflex.services.writeback_authority import build_source_file_snapshot

from ._support import snapshot

CONTENT = (
    b'\xef\xbb\xbf<?xml version="1.0" encoding="utf-8"?>\r\n<resources>\r\n'
    b'  <!-- another product -->\r\n  <string name="duplicate">One</string>\r\n'
    b'  <string name="selected">Original</string>\r\n'
    b'  <string name="duplicate"><![CDATA[Two & unchanged]]></string>\r\n'
    b"</resources>\r\n"
)


def source(content=CONTENT, **fields):
    return snapshot(
        content,
        repository_side="translations",
        path="shared/moko-resources/base/strings.xml",
        layout_identity="shared/moko-resources",
        **fields,
    )


def selection(s, key="selected", *, occurrence=0):
    value = [v for v in inspect_android_xml(s.parser_input).values if v.logical_key == key][
        occurrence
    ]
    return WriteEdit(key, value.language, value.selector, value.locator, value.display_text, "New")


def test_unique_edit_in_shared_catalog_preserves_every_unselected_byte():
    s = source()
    metadata = BitbucketSourceMetadata(s.authority.path, s.authority.commit_hash, len(CONTENT), ())
    verified = build_source_file_snapshot(s.authority, s.parser_input, metadata)
    output = render_file(verified, (selection(s),))
    assert output.content == CONTENT.replace(b">Original<", b">New<")
    assert output.changed_edits == (selection(s),)
    # Inspection for writing must never make duplicates canonical/importable.
    assert parse_canonical_snapshot(s.parser_input).issues[0].code == "duplicate_key"
    assert (
        parse_canonical_snapshot(replace(s.parser_input, content=output.content)).issues[0].code
        == "duplicate_key"
    )


@pytest.mark.parametrize("occurrence", [0, 1])
def test_selected_duplicate_is_rejected_even_with_an_exact_locator(occurrence):
    s = source()
    with pytest.raises(WritebackRejected) as error:
        render_file(s, (selection(s, "duplicate", occurrence=occurrence),))
    assert error.value.reason == WritebackReason.AMBIGUOUS_LOCATOR


def test_disjoint_plural_selectors_do_not_hide_duplicate_resource_names():
    s = source(
        b'<resources><plurals name="duplicate"><item quantity="one">One</item></plurals>'
        b'<plurals name="duplicate"><item quantity="other">Other</item></plurals></resources>'
    )
    with pytest.raises(WritebackRejected) as error:
        render_file(s, (selection(s, "duplicate"),))
    assert error.value.reason == WritebackReason.AMBIGUOUS_LOCATOR


def test_unsupported_content_after_duplicates_is_not_ignored():
    valid = source()
    s = source(CONTENT.replace(b"</resources>", b"<unsupported/></resources>"))
    with pytest.raises(WritebackRejected) as error:
        render_file(s, (selection(valid),))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


@pytest.mark.parametrize("field,value", [("expected_text", "stale"), ("language", "it")])
def test_shared_catalog_keeps_stale_and_foreign_selection_checks(field, value):
    s = source()
    with pytest.raises(WritebackRejected):
        render_file(s, (replace(selection(s), **{field: value}),))


def test_shared_catalog_keeps_exact_locator_check():
    s = source()
    change = selection(s)
    with pytest.raises(WritebackRejected) as error:
        render_file(s, (replace(change, locator=replace(change.locator, position=0)),))
    assert error.value.reason == WritebackReason.AMBIGUOUS_LOCATOR


def test_sequential_approved_snapshots_preserve_unrelated_duplicates():
    s = source()
    first = selection(s)
    second = replace(first, replacement_text="Later approval")
    assert render_file(s, (first,)).content == CONTENT.replace(b">Original<", b">New<")
    assert render_file(s, (second,)).content == CONTENT.replace(b">Original<", b">Later approval<")


def test_working_branch_overlay_preserves_unrelated_changes_across_approvals():
    from verboflex.localization.writing.branch_overlay import overlay_approved_moko

    s = source()
    working = CONTENT.replace(
        b"<resources>", b'<resources><string name="branch_only">Keep</string>'
    ).replace(b">One<", b">Unrelated branch edit<")
    first = selection(s)
    out = overlay_approved_moko(s, working, (first,), ())
    assert out == working.replace(b">Original<", b">New<")
    second = replace(first, replacement_text="Second approval")
    assert overlay_approved_moko(s, out, (second,), (first,)) == working.replace(
        b">Original<", b">Second approval<"
    )


@pytest.mark.parametrize(
    "before,after",
    [
        (b">Original<", b">Changed externally<"),
        (b'name="selected"', b'name="selected" formatted="false"'),
        (b'<string name="selected">Original</string>', b""),
        (b"</resources>", b'<string name="selected">Original</string></resources>'),
    ],
)
def test_working_branch_overlay_rejects_changed_missing_or_ambiguous_targets(before, after):
    from verboflex.localization.writing.branch_overlay import overlay_approved_moko

    s = source()
    with pytest.raises(WritebackRejected):
        overlay_approved_moko(s, CONTENT.replace(before, after), (selection(s),), ())


def test_working_branch_overlay_does_not_ignore_a_changed_previous_approval():
    from verboflex.localization.writing.branch_overlay import overlay_approved_moko

    s = source()
    first = selection(s)
    changed = CONTENT.replace(b">Original<", b">External change after approval<")
    with pytest.raises(WritebackRejected) as error:
        overlay_approved_moko(s, changed, (replace(first, replacement_text="Next"),), (first,))
    assert error.value.reason == WritebackReason.SOURCE_FILE_CHANGED
