from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_snapshot

FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization" / "xliff"


def _input(name: str, *, content: bytes | None = None, layout: str | None = None):
    return CanonicalParserInput(
        format="xliff",  # type: ignore[arg-type]
        repository_side="direct",
        path=f"locales/{name}",
        content=content if content is not None else (FIXTURES / name).read_bytes(),
        layout_identity=layout or f"xliff:locales/{name}",
        layout_version=1,
        base_language="en",
    )


@pytest.mark.parametrize("name", ["valid_12.xlf", "valid_20.xliff", "valid_21.xliff"])
def test_xliff_versions_parse_to_canonical_values(name: str) -> None:
    expected = json.loads(
        (FIXTURES / name.replace(Path(name).suffix, ".expected.json")).read_text()
    )
    result = parse_canonical_snapshot(_input(name))
    assert result.issues == ()
    assert len(result.values) == 1
    value = result.values[0]
    assert value.logical_key == expected["logical_key"]
    assert value.language == expected["language"]
    assert value.source_text == expected["source_text"]
    assert value.translated_text == expected["translated_text"]
    assert value.display_text == expected["translated_text"]
    assert value.locator.format == "xliff"
    assert dict(value.selector.fields)["dialect"] == expected["dialect"]
    assert tuple(node.kind for node in value.structure)[0] == "xliff:document"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b'<!DOCTYPE xliff [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><xliff/>', "malformed_file"),
        (b'<xliff xmlns="urn:wrong" version="1.2"/>', "unsupported_structure"),
        (
            b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="3.0"/>',
            "unsupported_structure",
        ),
        (b"\xff\xfe\x00\x00", "malformed_file"),
    ],
)
def test_xliff_rejects_hostile_or_unsupported_documents_atomically(
    content: bytes, code: str
) -> None:
    result = parse_canonical_snapshot(_input("unsafe.xlf", content=content))
    assert result.values == ()
    assert [issue.code for issue in result.issues] == [code]


def test_xliff_duplicate_unit_id_is_not_silently_overwritten() -> None:
    content = (
        b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="2.0" '
        b'srcLang="en" trgLang="it"><file id="f"><unit id="same"><segment>'
        b"<source>A</source><target>Uno</target></segment></unit>"
        b'<unit id="same"><segment><source>B</source><target>Due</target>'
        b"</segment></unit></file></xliff>"
    )
    result = parse_canonical_snapshot(_input("duplicate.xlf", content=content))
    assert result.values == ()
    assert [issue.code for issue in result.issues] == ["duplicate_key"]


def test_xliff_parse_is_deterministic_across_threads() -> None:
    parser_input = _input("valid_20.xliff")
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(parse_canonical_snapshot, [parser_input] * 16))
    assert all(result == results[0] for result in results)


def test_xliff_12_accepts_standard_schema_location_metadata() -> None:
    # Minimized from locize/xliff test/fixtures/example12.xliff (MIT).
    content = (
        b'<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" '
        b'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        b'xsi:schemaLocation="urn:oasis:names:tc:xliff:document:1.2 xliff-core-1.2.xsd" '
        b'version="1.2"><file original="messages" datatype="plaintext" '
        b'source-language="en-US" target-language="de-CH"><body>'
        b'<trans-unit id="hello"><source>Hello</source><target>Hallo</target>'
        b"</trans-unit></body></file></xliff>"
    )

    result = parse_canonical_snapshot(_input("schema-location.xliff", content=content))

    assert result.issues == ()
    assert [(value.logical_key, value.translated_text) for value in result.values] == [
        ("hello", "Hallo")
    ]


def test_xliff_21_accepts_core_skeleton_and_standard_xml_attributes() -> None:
    # Minimized from Symfony Translation Tests/Fixtures/resources-2.1.xlf (MIT).
    content = (
        b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="2.1" '
        b'srcLang="en-US" trgLang="ja-JP" xml:space="default">'
        b'<file id="f1" original="Graphic Example.psd"><skeleton href="Graphic Example.psd.skl"/>'
        b'<unit id="1"><segment><source xml:lang="en-US" xml:space="preserve">Quetzal</source>'
        b'<target xml:lang="ja-JP" xml:space="preserve">Quetzal</target></segment></unit>'
        b'<group id="g1" xml:space="preserve"><unit id="2"><segment>'
        b'<source>bar</source><target order="1">XLIFF data manager</target>'
        b"</segment></unit></group></file></xliff>"
    )

    result = parse_canonical_snapshot(_input("resources-2.1.xlf", content=content))

    assert result.issues == ()
    assert [(value.logical_key, value.translated_text) for value in result.values] == [
        ("1", "Quetzal"),
        ("2", "XLIFF data manager"),
    ]
    assert any(
        node.kind == "xliff:metadata" and dict(node.fields).get("name") == "skeleton"
        for node in result.values[0].structure
    )


def test_xliff_20_accepts_nonempty_internal_skeleton() -> None:
    # Boundary neighbor of the invalid empty/no-href skeleton fixture.
    content = (
        b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="2.0" '
        b'srcLang="en" trgLang="it"><file id="f"><skeleton>raw skeleton data</skeleton>'
        b'<unit id="u"><segment><source>Hello</source><target>Ciao</target>'
        b"</segment></unit></file></xliff>"
    )

    result = parse_canonical_snapshot(_input("internal-skeleton.xlf", content=content))

    assert result.issues == ()
    assert result.values[0].translated_text == "Ciao"


def test_xliff_rejects_unapproved_namespaced_attributes() -> None:
    content = (
        b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" xmlns:ext="urn:example" '
        b'version="2.0" srcLang="en" trgLang="it" ext:unsafe="value"><file id="f">'
        b'<unit id="u"><segment><source>Hello</source><target>Ciao</target>'
        b"</segment></unit></file></xliff>"
    )

    result = parse_canonical_snapshot(_input("extension.xlf", content=content))

    assert result.values == ()
    assert [issue.code for issue in result.issues] == ["unsupported_structure"]


_MICROSOFT_INVALID_CASES = {
    # Minimized from microsoft/XLIFF2-Object-Model Oasis_TestFiles/core/invalid (MIT).
    "bad_DifferentCopyOfInScAndEc.xlf": (
        b'<unit id="1"><segment><source><pc id="1">a</pc><pc id="2">b</pc></source>'
        b'<target><sc id="new" copyOf="1"/><ec startRef="new" copyOf="2"/></target>'
        b"</segment></unit>"
    ),
    "bad_InvalidXmlLangInheritedFromGroup.xlf": (
        b'<group id="g1" xml:lang="ja"><unit id="1"><segment>'
        b"<source>text</source><target>texte</target></segment></unit></group>"
    ),
    "bad_InvalidXmlLangOnGroup.xlf": (
        b'<group id="g1" xml:lang="ja"><unit id="1"><segment>'
        b"<source>text</source><target>texte</target></segment></unit></group>"
    ),
    "bad_OrderNotUnique1.xlf": (
        b'<unit id="1"><segment><source>s1</source><target order="1">t1</target></segment>'
        b'<segment><source>s2</source><target order="1">t2</target></segment></unit>'
    ),
    "bad_WrongReordering1.xlf": (
        b'<unit id="1"><segment><source><ph id="1" canReorder="firstNo" canDelete="no" '
        b'canCopy="no"/><ph id="2" canReorder="no" canDelete="no" canCopy="no"/>'
        b'<ph id="3" canReorder="no" canDelete="no" canCopy="no"/><ph id="5"/></source>'
        b'<target><ph id="1" canReorder="firstNo" canDelete="no" canCopy="no"/>'
        b'<ph id="2" canReorder="no" canDelete="no" canCopy="no"/><ph id="5"/>'
        b'<ph id="3" canReorder="no" canDelete="no" canCopy="no"/></target></segment></unit>'
    ),
    "bad_WrongReordering2.xlf": (
        b'<unit id="1"><segment><source><pc id="1" canReorder="firstNo" canDelete="no" '
        b'canCopy="no"><ph id="2" canReorder="no" canDelete="no" canCopy="no"/></pc></source>'
        b'<target><pc id="1" canReorder="firstNo" canDelete="no" canCopy="no"/>'
        b'<ph id="2" canReorder="no" canDelete="no" canCopy="no"/></target></segment></unit>'
    ),
    "bad_DifferentXmlSpace.xlf": (
        b'<unit id="1"><segment><source xml:space="preserve">source</source>'
        b"<target>target</target></segment></unit>"
    ),
    "bad_EmptySkeletonWithoutHref.xlf": (
        b'<skeleton/><unit id="1"><segment><source>source</source>'
        b"<target>target</target></segment></unit>"
    ),
    "bad_NonEmptySkeletonWithHref.xlf": (
        b'<skeleton href="skeleton.skl">some data</skeleton><unit id="1"><segment>'
        b"<source>source</source><target>target</target></segment></unit>"
    ),
    "bad_WrongSourceLang.xlf": (
        b'<unit id="1"><segment><source xml:lang="ja">source</source>'
        b"<target>target</target></segment></unit>"
    ),
    "bad_WrongTargetLang.xlf": (
        b'<unit id="1"><segment><source>source</source>'
        b'<target xml:lang="de">target</target></segment></unit>'
    ),
}


@pytest.mark.parametrize("name", tuple(_MICROSOFT_INVALID_CASES))
def test_xliff_2x_rejects_invalid_core_semantics_from_public_corpus(name: str) -> None:
    content = (
        b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="2.0" '
        b'srcLang="en" trgLang="fr"><file id="f1">'
        + _MICROSOFT_INVALID_CASES[name]
        + b"</file></xliff>"
    )

    result = parse_canonical_snapshot(_input(name, content=content))

    assert result.values == ()
    assert [issue.code for issue in result.issues] == ["unsupported_structure"]
