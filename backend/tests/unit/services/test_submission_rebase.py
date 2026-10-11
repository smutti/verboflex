"""Replay frozen approved edits on a changed base without altering other resources."""

from dataclasses import replace

import pytest

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.writing.core import WritebackRejected, WriteEdit
from verboflex.localization.writing.rebase import replay_approved_edits


def android_edit():
    parser = CanonicalParserInput(
        "android_xml",
        "direct",
        "app/res/values-it/strings.xml",
        b'<resources><string name="edit">old</string></resources>',
        "app/res",
        1,
        "en",
    )
    value = parse_canonical_snapshot(parser).values[0]
    edit = WriteEdit(
        value.logical_key,
        value.language,
        value.selector,
        value.locator,
        value.display_text,
        "Approved %1$s",
    )
    return parser, edit


def test_android_rebase_preserves_new_base_resources_and_approved_placeholder():
    parser, edit = android_edit()
    base = (
        b'<resources>\n<!-- upstream -->\n<string name="added">New</string>\n'
        b'<string name="edit">Concurrent change</string>\n</resources>'
    )
    expected = base.replace(b"Concurrent change", b"Approved %1$s")
    assert replay_approved_edits(replace(parser, content=base), (edit,)) == expected


def test_already_applied_edit_keeps_current_bytes():
    parser, edit = android_edit()
    base = parser.content.replace(b"old", b"Approved %1$s")
    assert replay_approved_edits(replace(parser, content=base), (edit,)) == base


@pytest.mark.parametrize(
    "base",
    [
        b'<resources><string name="other">old</string></resources>',
        b'<resources><string name="edit">a</string><string name="edit">b</string></resources>',
        b"<resources>invalid",
    ],
)
def test_missing_ambiguous_or_invalid_resources_require_review(base):
    parser, edit = android_edit()
    with pytest.raises(WritebackRejected):
        replay_approved_edits(replace(parser, content=base), (edit,))


@pytest.mark.parametrize(
    "format_name,path,layout,before,base,expected",
    [
        (
            "json",
            "it.json",
            "json:flat-per-locale:{locale}.json",
            b'{"k":"old"}',
            b'{"added":"new", "k":"concurrent"}',
            b'{"added":"new", "k":"approved"}',
        ),
        (
            "ios_strings",
            "it.lproj/Localizable.strings",
            "ios-strings:{locale}.lproj/Localizable.strings",
            b'"k"="old";',
            b'/* upstream */ "added"="new"; "k"="concurrent";',
            b'/* upstream */ "added"="new"; "k"="approved";',
        ),
        (
            "qt_ts",
            "app_it.ts",
            "qt-ts:app_{locale}.ts",
            b'<TS version="2.1" language="it"><context><name>Main</name>'
            b'<message id="k"><source>Source</source><translation>old</translation>'
            b"</message></context></TS>",
            b'<TS version="2.1" language="it">\n<context><name>Main</name>'
            b'<message id="k"><source>Source</source><translation>concurrent</translation>'
            b"</message></context></TS>",
            b'<TS version="2.1" language="it">\n<context><name>Main</name>'
            b'<message id="k"><source>Source</source><translation>approved</translation>'
            b"</message></context></TS>",
        ),
    ],
)
def test_other_formats_preserve_unrelated_base_bytes(
    format_name, path, layout, before, base, expected
):
    parser = CanonicalParserInput(format_name, "direct", path, before, layout, 1, "en")
    value = parse_canonical_snapshot(parser).values[0]
    edit = WriteEdit(
        value.logical_key,
        value.language,
        value.selector,
        value.locator,
        value.display_text,
        "approved",
    )
    assert replay_approved_edits(replace(parser, content=base), (edit,)) == expected


def test_android_authored_key_replay_and_collision():
    from verboflex.localization.writing.core import WriteInsert

    parser, edit = android_edit()
    insert = WriteInsert("edit", edit.language, edit.selector, "Approved %1$s")
    empty = replace(parser, content=b'<resources><string name="added">New</string></resources>')
    result = replay_approved_edits(empty, (insert,))
    values = parse_canonical_snapshot(replace(parser, content=result)).values
    assert {v.logical_key: v.display_text for v in values} == {
        "added": "New",
        "edit": "Approved %1$s",
    }
    assert replay_approved_edits(replace(parser, content=result), (insert,)) == result
    with pytest.raises(WritebackRejected):
        replay_approved_edits(parser, (insert,))
