"""MOKO uses exact source paths and explicit, non-inferred base authority."""

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_mapping
from verboflex.localization.preview.registry import detect_preview_layouts
from verboflex.services.repository_discovery import RepositorySourceFile


def sources():
    return (
        RepositorySourceFile(
            "module/moko-resources/base/strings.xml",
            b'<resources><string name="title" translatable="true">Hello <b>world</b></string>'
            b'<string name="id" translatable="false">APP</string></resources>',
        ),
        RepositorySourceFile(
            "module/moko-resources/it/strings.xml",
            b'<resources><string name="title">Ciao <u>mondo</u></string></resources>',
        ),
    )


def test_moko_preview_uses_default_marker_and_complete_paths():
    result = detect_preview_layouts(sources(), repository_side="direct")
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.format == "android_xml"
    assert candidate.layout_identity == "module/moko-resources"
    assert candidate.languages == ("default", "it")
    assert candidate.files == tuple(file.path for file in sources())


def test_moko_canonical_preserves_markup_metadata_and_explicit_base():
    result = parse_canonical_mapping(
        tuple(
            CanonicalParserInput(
                format="android_xml",
                repository_side="direct",
                path=file.path,
                content=file.content,
                layout_identity="module/moko-resources",
                layout_version=1,
                base_language="fr",
            )
            for file in sources()
        )
    )
    assert result.issues == ()
    assert len(result.values) == 3
    base = next(
        value for value in result.values if value.logical_key == "title" and value.language == "fr"
    )
    assert base.locator.path == "module/moko-resources/base/strings.xml"
    assert any(node.kind == "android_xml:inline" for node in base.structure)
    nontranslatable = next(value for value in result.values if value.logical_key == "id")
    assert ("translatable", False) in nontranslatable.structure[0].fields


def test_unrecognized_xml_peer_inside_moko_root_blocks_the_whole_layout():
    valid = RepositorySourceFile(
        path="moko-resources/base/strings.xml",
        content=b'<resources><string name="ok">Hello</string></resources>',
    )
    unsupported = RepositorySourceFile(
        path="moko-resources/invalid_locale/strings.xml",
        content=b'<resources><string name="ok">Hidden</string></resources>',
    )
    assert detect_preview_layouts((valid, unsupported), repository_side="direct").candidates == ()
