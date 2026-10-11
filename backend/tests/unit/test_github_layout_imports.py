"""Real repository layout regressions at the confirmed-import boundary."""

from verboflex.localization.preview.core import build_layout_candidate
from verboflex.services.import_jobs import (
    _unrelated_android_resource,
    confirmed_file_parser_input,
)


def test_exact_qt_assignments_resolve_overlapping_templates_but_new_ambiguity_fails():
    general = build_layout_candidate(
        repository_side="direct",
        format="qt_ts",
        layout_identity="qt-ts:translations/App_{locale}.ts",
        files=("translations/App_en.ts",),
        values={"en": {"hello": "Hello"}},
    )
    specific = build_layout_candidate(
        repository_side="direct",
        format="qt_ts",
        layout_identity="qt-ts:translations/App_de_{locale}.ts",
        files=("translations/App_de_DE.ts",),
        values={"de": {"hello": "Hallo"}},
    )
    for path, expected in (
        ("translations/App_en.ts", general),
        ("translations/App_de_DE.ts", specific),
        ("translations/App_it.ts", general),
    ):
        result = confirmed_file_parser_input(
            (general, specific),
            repository_side="direct",
            path=path,
            content=b"<TS/>",
            base_language="en",
        )
        assert result is not None
        assert result.layout_identity == expected.layout_identity
    assert (
        confirmed_file_parser_input(
            (general, specific),
            repository_side="direct",
            path="translations/App_de_AT.ts",
            content=b"<TS/>",
            base_language="en",
        )
        is None
    )


def test_android_nonlocalization_resources_are_ignored_but_malformed_strings_are_not():
    candidate = build_layout_candidate(
        repository_side="direct",
        format="android_xml",
        layout_identity="app/res",
        files=("app/res/values/strings.xml",),
        values={"default": {"hello": "Hello"}},
    )
    assert _unrelated_android_resource(
        candidate, b'<resources><color name="bg">#fff</color></resources>'
    )
    assert not _unrelated_android_resource(candidate, b'<resources><string name="hello">')
    assert not _unrelated_android_resource(
        candidate, b'<resources><string name="hello">Hello</string></resources>'
    )


def test_json_refresh_accepts_new_supported_locale_and_keeps_malformed_content_visible():
    candidate = build_layout_candidate(
        repository_side="direct",
        format="json",
        layout_identity="json:flat-per-locale:src/lang/{locale}.json",
        files=("src/lang/en.json",),
        values={"en": {"hello": "Hello"}},
    )
    assert (
        confirmed_file_parser_input(
            (candidate,),
            repository_side="direct",
            path="src/lang/fr.json",
            content=b"{",
            base_language="en",
        )
        is not None
    )
    assert (
        confirmed_file_parser_input(
            (candidate,),
            repository_side="direct",
            path="src/lang/ca@valencia.json",
            content=b'{"hello":"Hola"}',
            base_language="en",
        )
        is None
    )
