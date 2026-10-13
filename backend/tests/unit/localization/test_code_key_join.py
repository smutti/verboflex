from verboflex.localization.code_keys.catalog import CodeSourceConfig, extract_catalog
from verboflex.localization.code_keys.join import join_code_translations
from verboflex.localization.importing.core import CanonicalParserInput


def test_join_uses_real_base_text_and_keeps_translation_provenance() -> None:
    catalog = extract_catalog(
        {"Keys.kt": b'const val TITLE = "title"\nconst val MISSING = "missing"'},
        CodeSourceConfig(resource_roots=(), declaration_symbols=("*",)),
    )
    inputs = tuple(
        CanonicalParserInput(
            format="android_xml",
            repository_side="translations",
            path=f"shared/moko-resources/{locale}/strings.xml",
            content=content,
            layout_identity="shared/moko-resources",
            layout_version=1,
            base_language="en",
        )
        for locale, content in (
            (
                "base",
                b'<resources><string name="title">Welcome</string>'
                b'<string name="orphan">Extra</string></resources>',
            ),
            ("it", b'<resources><string name="title">Benvenuto</string></resources>'),
        )
    )
    joined = join_code_translations(catalog, inputs)
    assert not joined.result.issues
    assert joined.missing_keys == ("missing",)
    assert joined.orphan_keys == ("orphan",)
    assert {v.logical_key for v in joined.result.values} == {"title"}
    italian = next(v for v in joined.result.values if v.language == "it")
    assert italian.source_text == "Welcome"
    assert italian.translated_text == "Benvenuto"
    assert italian.locator.repository_side == "translations"
    assert italian.locator.path == "shared/moko-resources/it/strings.xml"


def test_key_without_base_has_no_invented_source() -> None:
    catalog = extract_catalog(
        {"Screen.kt": b"fun screen() = Res.strings.title"}, CodeSourceConfig()
    )
    joined = join_code_translations(
        catalog,
        (
            CanonicalParserInput(
                format="android_xml",
                repository_side="translations",
                path="res/values-it/strings.xml",
                content=b'<resources><string name="title">Ciao</string></resources>',
                layout_identity="res",
                layout_version=1,
                base_language="en",
            ),
        ),
    )
    assert joined.result.values[0].source_text is None
    assert joined.missing_base_keys == ("title",)


def test_malformed_translation_prevents_partial_activation() -> None:
    catalog = extract_catalog(
        {"Screen.kt": b"fun screen() = Res.strings.title"}, CodeSourceConfig()
    )
    joined = join_code_translations(
        catalog,
        (
            CanonicalParserInput(
                format="android_xml",
                repository_side="translations",
                path="res/values/strings.xml",
                content=b"<resources>",
                layout_identity="res",
                layout_version=1,
                base_language="en",
            ),
        ),
    )
    assert joined.result.issues
    assert joined.result.values == ()
    assert all(issue.repository_side == "translations" for issue in joined.result.issues)


def test_join_rejects_source_files_from_any_other_repository_side():
    from dataclasses import replace

    import pytest

    catalog = extract_catalog({"Screen.kt": b"fun title() = Res.strings.title"}, CodeSourceConfig())
    parser = CanonicalParserInput(
        format="android_xml",
        repository_side="translations",
        path="res/values/strings.xml",
        content=b'<resources><string name="title">Hello</string></resources>',
        layout_identity="res",
        layout_version=1,
        base_language="en",
    )
    for side in ("keys", "direct"):
        with pytest.raises(ValueError, match="separate translations"):
            join_code_translations(catalog, (replace(parser, repository_side=side),))
