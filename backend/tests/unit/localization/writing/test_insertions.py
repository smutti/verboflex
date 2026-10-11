"""Structural additions must preserve existing resources and reject collisions."""

from dataclasses import replace

import pytest

from verboflex.localization.importing.core import CanonicalSelector
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.writing.core import WritebackRejected, WriteInsert
from verboflex.localization.writing.registry import render_file

from ._support import edit, snapshot


@pytest.mark.parametrize(
    "content,fields,selector,language",
    [
        (
            b'<resources><!-- keep --><string name="old">Old</string></resources>',
            {},
            CanonicalSelector("scalar", ()),
            "en",
        ),
        (
            b'{ "old" : "Old" }',
            dict(
                format="json", path="en.json", layout_identity="json:flat-per-locale:{locale}.json"
            ),
            CanonicalSelector("json_path", (("parents", ()),)),
            "en",
        ),
        (
            '/* keep */ "old" = "Old";'.encode("utf-16"),
            dict(
                format="ios_strings",
                path="en.lproj/Localizable.strings",
                layout_identity="ios-strings:{locale}.lproj/Localizable.strings",
            ),
            CanonicalSelector("scalar", ()),
            "en",
        ),
        (
            b'<TS version="2.1" language="it"><context><name>Main</name>'
            b'<message id="old"><source>Old</source><translation>Vecchio</translation>'
            b"</message></context></TS>",
            dict(format="qt_ts", path="app_it.ts", layout_identity="qt-ts:app_{locale}.ts"),
            CanonicalSelector("scalar", (("identity_kind", "id"),)),
            "it",
        ),
    ],
)
def test_insert_and_edit_reparse_without_changing_unselected_content(
    content, fields, selector, language
):
    source = snapshot(content, **fields)
    addition = WriteInsert("new", language, selector, 'Hello & "world"', "Hello", "Main")
    result = render_file(source, (addition,))
    parsed = parse_canonical_snapshot(replace(source.parser_input, content=result.content))
    assert not parsed.issues
    assert [(v.logical_key, v.display_text) for v in parsed.values] == [
        ("old", "Vecchio" if language == "it" else "Old"),
        ("new", 'Hello & "world"'),
    ]
    assert result.changed_edits == (addition,)
    combined = render_file(source, (edit(source, "old", "Updated"), addition))
    reparsed = parse_canonical_snapshot(replace(source.parser_input, content=combined.content))
    assert reparsed.values[0].display_text == "Updated"
    with pytest.raises(WritebackRejected):
        render_file(source, (replace(addition, logical_key="old"),))


def test_json_nested_insertion_preserves_literal_key_and_other_locale():
    source = snapshot(
        b'{"en":{"screen":{"old":"Keep"}},"it":{"old":"Tieni"}}',
        format="json",
        path="locales.json",
        layout_identity="json:locale-rooted:locales.json",
    )
    addition = WriteInsert(
        "literal.dot", "en", CanonicalSelector("json_path", (("parents", ("screen",)),)), "New"
    )
    result = render_file(source, (addition,))
    assert b'"it":{"old":"Tieni"}' in result.content
    assert b'"old":"Keep"' in result.content
    assert not parse_canonical_snapshot(replace(source.parser_input, content=result.content)).issues


def test_addition_in_wrong_file_language_is_rejected():
    source = snapshot(b'<resources><string name="old">Old</string></resources>')
    with pytest.raises(WritebackRejected):
        render_file(source, (WriteInsert("new", "it", CanonicalSelector("scalar", ()), "New"),))


def test_multiple_insertions_and_empty_document():
    source = snapshot(b"<resources/>")
    edits = tuple(
        WriteInsert(key, "en", CanonicalSelector("scalar", ()), key) for key in ("first", "second")
    )
    result = render_file(source, edits)
    assert b'<string name="first">first</string>' in result.content
    assert b'<string name="second">second</string>' in result.content
    with pytest.raises(WritebackRejected):
        render_file(source, (edits[0], edits[0]))


@pytest.mark.parametrize(
    "language,forms",
    [
        ("en", ("one", "other")),
        ("it", ("one", "many", "other")),
        ("vi", ("other",)),
        ("ar", ("zero", "one", "two", "few", "many", "other")),
    ],
)
def test_android_native_plural_insertions_follow_language_profile(language, forms):
    from verboflex.localization.plural_forms import plural_forms

    assert tuple(key for key, _ in plural_forms("android_xml", language)) == forms
    source = snapshot(
        b'<resources><string name="old">Old</string></resources>',
        path=f"app/src/main/res/values-{language}/strings.xml",
    )
    operations = tuple(
        WriteInsert(
            "count",
            language,
            CanonicalSelector("android_quantity", (("quantity", form),)),
            f"%d {form}",
        )
        for form in forms
    )
    result = render_file(source, operations)
    values = parse_canonical_snapshot(replace(source.parser_input, content=result.content)).values
    assert len(values) == len(forms) + 1
    assert b'<string name="old">Old</string>' in result.content


@pytest.mark.parametrize("language,count", [("it", 2), ("vi", 1), ("ar", 6), ("ru", 3)])
def test_qt_native_plural_forms_have_runtime_order(language, count):
    from verboflex.localization.plural_forms import plural_forms

    assert len(plural_forms("qt_ts", language)) == count
    source = snapshot(
        (
            f'<TS version="2.1" language="{language}"><context><name>Main</name></context></TS>'
        ).encode(),
        format="qt_ts",
        path=f"app_{language}.ts",
        layout_identity="qt-ts:app_{locale}.ts",
    )
    operations = tuple(
        WriteInsert(
            "%n files",
            language,
            CanonicalSelector(
                "qt_numerus", (("identity_kind", "source"), ("context", "Main"), ("form_index", i))
            ),
            f"%n form {i}",
            "%n files",
            "Main",
        )
        for i in range(count)
    )
    result = render_file(source, operations)
    assert result.content.count(b"<numerusform>") == count
    assert (
        len(parse_canonical_snapshot(replace(source.parser_input, content=result.content)).values)
        == count
    )


def test_authoring_detects_prefixed_qt_filename_language():
    from types import SimpleNamespace

    from verboflex.services.translation_authoring import file_languages

    source = snapshot(
        b"",
        format="qt_ts",
        path="data/translations/Internationalization_ar.ts",
        layout_identity="qt-ts:data/translations/Internationalization_{locale}.ts",
    )
    assert file_languages(source.parser_input, SimpleNamespace(language_counts={})) == ["ar"]
