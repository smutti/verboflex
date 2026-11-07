"""New-language output preserves catalog identities and source bytes."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.languages import initialize_language

FIXTURES = Path(__file__).parents[2] / "fixtures/localization"


def parser(format, path, content, layout):
    return CanonicalParserInput(
        format=format,
        repository_side="direct",
        path=path,
        content=content,
        layout_identity=layout,
        layout_version=1,
        base_language="en",
    )


@pytest.mark.parametrize(
    "source,target",
    [
        (
            parser(
                "json",
                "locales/en.json",
                b'{\n "A":{"NAME":"Hello {{ name }}", "EMPTY":{}},"B":{"NAME":"%1$s"}\n}',
                "json:flat-per-locale:locales/{locale}.json",
            ),
            "locales/fr-BE.json",
        ),
        (
            parser(
                "ios_strings",
                "app/Base.lproj/Localizable.strings",
                '// Preserve accents\r\n"welcome" = "Hello %@";\r\n'.encode("utf-16"),
                "ios-strings:app/{locale}.lproj/Localizable.strings",
            ),
            "app/fr-BE.lproj/Localizable.strings",
        ),
        (
            parser(
                "android_xml",
                "app/res/values/strings.xml",
                (
                    b'<resources><!--keep--><string name="hello">Hello %1$s</string><strin'
                    b'g-array name="items"><item>A</item><item>B</item></string-array></re'
                    b"sources>"
                ),
                "app/res",
            ),
            "app/res/values-fr-rBE/strings.xml",
        ),
        (
            parser(
                "android_xml",
                "shared/moko-resources/base/strings.xml",
                b'<resources><!--keep--><string name="hello">Hello %1$s</string></resources>',
                "shared/moko-resources",
            ),
            "shared/moko-resources/fr-BE/strings.xml",
        ),
        (
            parser(
                "html",
                "mail/Welcome_EN.html",
                b'<!DOCTYPE html><html><body><p class="same">Hello {{name}}</p></body></html>',
                "html:mail",
            ),
            "mail/Welcome_FR-BE.html",
        ),
    ],
)
def test_new_peer_copies_every_byte_and_preserves_all_keys(source, target):
    result = initialize_language(source, "fr-BE")
    assert result.path == target and result.new_file
    assert result.content == source.content
    before = parse_canonical_snapshot(source)
    after = parse_canonical_snapshot(replace(source, path=target, content=result.content))
    assert not after.issues
    assert [(v.logical_key, v.selector, v.display_text) for v in before.values] == [
        (v.logical_key, v.selector, v.display_text) for v in after.values
    ]
    assert {v.language for v in after.values} == {"fr-BE"}


def test_shared_json_adds_one_locale_without_changing_any_existing_bytes():
    content = (
        b'{ "en": {"MENU":{"NAME":"Hello {{name}}"}}, "it":{"MENU":{"NAME":"Ciao {{name}}"}}\n}'
    )
    source = parser("json", "catalog.json", content, "json:locale-rooted:catalog.json")
    created = initialize_language(source, "de")
    assert created.path == source.path and not created.new_file
    assert created.content.startswith(content[:-1])
    assert json.loads(created.content)["de"] == json.loads(content)["en"]
    assert {k: v for k, v in json.loads(created.content).items() if k != "de"} == json.loads(
        content
    )
    with pytest.raises(ValueError, match="language_exists"):
        initialize_language(replace(source, content=created.content), "de")


def test_android_adds_arabic_plural_forms_with_original_placeholder():
    content = (
        b'<resources><plurals name="count"><item quantity="one">%d item</item>'
        b'<item quantity="other">%d items</item></plurals></resources>'
    )
    source = parser("android_xml", "res/values/strings.xml", content, "res")
    created = initialize_language(source, "ar")
    result = parse_canonical_snapshot(replace(source, path=created.path, content=created.content))
    assert not result.issues
    assert len(result.values) == 6
    assert all("%d" in v.display_text for v in result.values)
    assert (
        b'<item quantity="one">%d item</item><item quantity="other">%d items</item>'
        in created.content
    )


@pytest.mark.parametrize("language,count", [("ar", 6), ("vi", 1)])
def test_qt_copies_metadata_and_initializes_destination_plural_count(language, count):
    content = (
        b'<?xml version="1.0"?><!DOCTYPE TS><TS version="2.1" language="en"><c'
        b'ontext><name>Main</name><comment>keep</comment><message id="count" n'
        b'umerus="yes"><source>%n item</source><translation><numerusform>%n it'
        b"em</numerusform><numerusform>%n items</numerusform></translation></m"
        b"essage></context></TS>"
    )
    source = parser("qt_ts", "messages_en.ts", content, "qt-ts:messages_{locale}.ts")
    created = initialize_language(source, language)
    result = parse_canonical_snapshot(replace(source, path=created.path, content=created.content))
    assert not result.issues
    assert len(result.values) == count
    assert {v.logical_key for v in result.values} == {"count"}
    assert all("%n" in v.display_text for v in result.values)
    assert b"<comment>keep</comment>" in created.content and b"<!DOCTYPE TS>" in created.content
    assert b'type="unfinished"' in created.content


@pytest.mark.parametrize(
    "fixture,locale",
    [("valid_12.xlf", "it-IT"), ("valid_20.xliff", "fr-FR"), ("valid_21.xliff", "ja-JP")],
)
def test_xliff_preserves_inline_codes_and_initializes_from_source(fixture, locale):
    content = (FIXTURES / "xliff" / fixture).read_bytes()
    suffix = Path(fixture).suffix
    source = parser(
        "xliff", f"messages/{locale}{suffix}", content, f"xliff:messages/{{locale}}{suffix}"
    )
    created = initialize_language(source, "nl")
    before = parse_canonical_snapshot(source)
    result = parse_canonical_snapshot(replace(source, path=created.path, content=created.content))
    assert not result.issues
    assert [(v.logical_key, v.source_text) for v in before.values] == [
        (v.logical_key, v.display_text) for v in result.values
    ]
    assert {v.language for v in result.values} == {"nl"}
    for marker in (b'<ph id="1"/>', b'<g id="name">'):
        if marker in content:
            assert marker in created.content


@pytest.mark.parametrize("locale", ["../fr", "FR", "fr/it", "fr\n", "en"])
def test_invalid_or_existing_locale_never_yields_a_file(locale):
    source = parser(
        "json", "en.json", b'{"key":"Hello {{ name }}"}', "json:flat-per-locale:{locale}.json"
    )
    with pytest.raises(ValueError):
        initialize_language(source, locale)


def test_ambiguous_path_and_malformed_source_fail_closed():
    source = parser(
        "qt_ts",
        "messages.ts",
        (
            b'<TS version="2.1" language="en"><context><name>Main</name><message><'
            b"source>Hi</source><translation>Hi</translation></message></context><"
            b"/TS>"
        ),
        "qt-ts:messages.ts",
    )
    with pytest.raises(ValueError, match="ambiguous_language_path"):
        initialize_language(source, "it")
    with pytest.raises(ValueError, match="unsupported_shape"):
        initialize_language(
            replace(
                source, content=b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]><x>&a;</x>'
            ),
            "it",
        )


@pytest.mark.parametrize(
    "locale,folder", [("sr-Latn-RS", "values-b+sr+Latn+RS"), ("es-419", "values-b+es+419")]
)
def test_android_script_and_numeric_region_follow_bcp47_layout(locale, folder):
    from verboflex.localization.preview.registry import detect_preview_layouts
    from verboflex.services.repository_discovery import RepositorySourceFile

    content = b'<resources><string name="hello">Hello %s</string></resources>'
    source = parser("android_xml", "res/values/strings.xml", content, "res")
    created = initialize_language(source, locale)
    assert created.path == f"res/{folder}/strings.xml"
    assert created.content == content
    preview = detect_preview_layouts(
        (RepositorySourceFile(created.path, content),), repository_side="direct"
    )
    assert preview.candidates[0].languages == (locale,)


def test_shared_moko_keeps_unrelated_duplicate_keys_when_copying():
    content = (
        b'<resources><string name="hello">Hello %s</string>'
        b'<string name="other">One</string><string name="other">Two</string></resources>'
    )
    source = replace(
        parser("android_xml", "moko-resources/base/strings.xml", content, "moko-resources"),
        repository_side="translations",
    )
    created = initialize_language(source, "de")
    assert created.content == content
    assert created.path == "moko-resources/de/strings.xml"


@pytest.mark.parametrize("target", [b"<translation/>", b'<translation type="unfinished"/>'])
def test_empty_qt_target_copies_source_but_remains_unfinished(target):
    source = parser(
        "qt_ts",
        "en.ts",
        b'<TS version="2.1" language="en"><context><name>Main</name><message>'
        b"<source>Hello %1</source>" + target + b"</message></context></TS>",
        "qt-ts:{locale}.ts",
    )
    result = initialize_language(source, "fr")
    assert b'<translation type="unfinished">Hello %1</translation>' in result.content


def test_empty_qt_plural_forms_copy_source_placeholders_in_every_new_form():
    source = parser(
        "qt_ts",
        "en.ts",
        b'<TS version="2.1" language="en"><context><name>Main</name><message numerus="yes">'
        b"<source>%n items</source><translation><numerusform/><numerusform/></translation>"
        b"</message></context></TS>",
        "qt-ts:{locale}.ts",
    )
    result = initialize_language(source, "ar")
    assert result.content.count(b"<numerusform>%n items</numerusform>") == 6
    assert b'type="unfinished"' in result.content


def test_empty_xliff_target_is_expanded_and_marked_needs_translation():
    content = (FIXTURES / "xliff/valid_12.xlf").read_bytes()
    content = content.replace(b'<trans-unit id=', b'<trans-unit approved="yes" id=')
    content = content.replace(b'<target>Ciao <g id="name">amico</g></target>', b"<target/>")
    source = parser("xliff", "it-IT.xlf", content, "xliff:{locale}.xlf")
    result = initialize_language(source, "nl")
    assert b'<trans-unit approved="no" id=' in result.content
    assert (
        b'<target state="needs-translation">Hello <g id="name">friend</g></target>'
        in result.content
    )
