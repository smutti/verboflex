"""Canonical Android XML scalar adapter contracts."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

_FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization" / "android"


def _canonical_modules() -> tuple[Any, Any]:
    """Resolve production modules while making a missing adapter a behavioral RED."""
    try:
        core = importlib.import_module("verboflex.localization.importing.core")
        registry = importlib.import_module("verboflex.localization.importing.registry")
    except ModuleNotFoundError:
        pytest.fail("canonical Android adapter is not implemented")
    return core, registry


def _input(**overrides: object) -> object:
    core, _ = _canonical_modules()
    fields: dict[str, object] = {
        "format": "android_xml",
        "repository_side": "direct",
        "path": "app/src/main/res/values/strings.xml",
        "content": (_FIXTURES / "scalar.xml").read_bytes(),
        "layout_identity": "app/src/main/res",
        "layout_version": 1,
        "base_language": "en_US",
    }
    fields.update(overrides)
    return core.CanonicalParserInput(**fields)


def test_android_scalar_snapshot_is_canonical_and_immutable() -> None:
    core, registry = _canonical_modules()

    parser_input = _input()
    result = registry.parse_canonical_snapshot(parser_input)

    assert result.issues == ()
    assert len(result.values) == 1
    value = result.values[0]
    assert value.logical_key == "welcome.title"
    assert value.language == "en-US"
    assert value.selector == core.CanonicalSelector(kind="scalar", fields=())
    assert value.source_text == "Hello, world!"
    assert value.translated_text is None
    assert value.display_text == "Hello, world!"
    assert value.structure == (
        core.CanonicalStructureNode(
            kind="android_xml:string",
            fields=(("translatable", True), ("formatted", False)),
        ),
        core.CanonicalStructureNode(
            kind="android_xml:text",
            fields=(("value", "Hello, world!"),),
        ),
    )
    assert value.locator == core.CanonicalLocator(
        format="android_xml",
        repository_side="direct",
        path="app/src/main/res/values/strings.xml",
        position=0,
        structural_address=("resources", "string", 0),
    )

    with pytest.raises(AttributeError):
        value.language = "it"


@pytest.mark.parametrize(
    ("content", "expected_code"),
    (
        (
            b"<!DOCTYPE resources [<!ENTITY x 'secret'>]>"
            b"<resources><string name='welcome.title'>&x;</string></resources>",
            "malformed_file",
        ),
        (
            b"<resources unknown='x'><string name='key'>value</string></resources>",
            "unsupported_structure",
        ),
        (b"<resources><plurals name='count'/></resources>", "unsupported_structure"),
        (
            b"<resources><string name='key'><b>value</b></string></resources>",
            "unsupported_structure",
        ),
        (
            b"<resources><string name='key' unknown='x'>value</string></resources>",
            "unsupported_structure",
        ),
        (b"<resources><string name='key'>value</resources>", "malformed_file"),
        (b"\xff<resources><string name='key'>value</string></resources>", "malformed_file"),
    ),
)
def test_android_scalar_failures_are_atomic_and_closed(
    content: bytes,
    expected_code: str,
) -> None:
    _, registry = _canonical_modules()

    result = registry.parse_canonical_snapshot(_input(content=content))

    assert result.values == ()
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.code == expected_code
    assert issue.repository_side == "direct"
    assert issue.path == "app/src/main/res/values/strings.xml"
    assert len(issue.message) <= 256
    assert "secret" not in issue.message
    assert "<" not in issue.message


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    (
        ({"format": "unknown"}, "unsupported_structure"),
        ({"layout_identity": "another/res"}, "ambiguous_structure"),
        ({"layout_version": 2}, "ambiguous_structure"),
        ({"base_language": ""}, "base_language_required"),
    ),
)
def test_android_scalar_rejects_invalid_confirmed_authority(
    overrides: dict[str, object],
    expected_code: str,
) -> None:
    _, registry = _canonical_modules()

    result = registry.parse_canonical_snapshot(_input(**overrides))

    assert result.values == ()
    assert tuple(issue.code for issue in result.issues) == (expected_code,)


def test_android_scalar_rejects_an_unrecognized_input_field() -> None:
    _, registry = _canonical_modules()
    input_with_extra_field = {
        "format": "android_xml",
        "repository_side": "direct",
        "path": "app/src/main/res/values/strings.xml",
        "content": (_FIXTURES / "scalar.xml").read_bytes(),
        "layout_identity": "app/src/main/res",
        "layout_version": 1,
        "base_language": "en",
        "source_fragment": "must not cross the parser boundary",
    }

    result = registry.parse_canonical_snapshot(cast(Any, input_with_extra_field))

    assert result.values == ()
    assert tuple(issue.code for issue in result.issues) == ("malformed_file",)


def test_android_structured_markup_and_escape_golden_manifest() -> None:
    core, registry = _canonical_modules()
    source = (_FIXTURES / "valid_structured.xml").read_bytes()
    expected = json.loads((_FIXTURES / "valid_structured.expected.json").read_text())

    result = registry.parse_canonical_snapshot(
        _input(
            path="app/src/main/res/values-it/strings.xml",
            content=source,
        )
    )

    assert result.to_mapping() == expected
    assert tuple(value.logical_key for value in result.values) == (
        "escaped",
        "files",
        "files",
        "markup",
        "steps",
        "steps",
    )
    assert {
        (value.logical_key, value.selector.kind, tuple(value.selector.fields))
        for value in result.values
    } == {
        ("escaped", "scalar", ()),
        ("markup", "scalar", ()),
        ("files", "android_quantity", (("quantity", "one"),)),
        ("files", "android_quantity", (("quantity", "other"),)),
        ("steps", "android_array_item", (("index", 0),)),
        ("steps", "android_array_item", (("index", 1),)),
    }
    markup = next(value for value in result.values if value.logical_key == "markup")
    assert markup.display_text == "Hello <literal>bold and italic tail %1$d!"
    assert tuple(node.kind for node in markup.structure).count("android_xml:cdata") == 1
    assert tuple(node.kind for node in markup.structure).count("android_xml:comment") == 1
    assert core.CanonicalStructureNode(
        kind="android_xml:inline",
        fields=(
            ("event", "start"),
            ("name", "g"),
            ("namespace", "urn:oasis:names:tc:xliff:document:1.2"),
            ("id", "count"),
            ("example", "2"),
        ),
    ) in markup.structure


@pytest.mark.parametrize(
    ("content", "expected_code"),
    (
        (b"<resources><color name='x'>red</color></resources>", "unsupported_structure"),
        (b"<resources><plurals name='x' formatted='true'/></resources>", "unsupported_structure"),
        (
            b"<resources><string-array name='x' formatted='true'/></resources>",
            "unsupported_structure",
        ),
        (
            b"<resources><plurals name='x'><item quantity='invalid'>x</item></plurals>"
            b"</resources>",
            "unsupported_structure",
        ),
        (
            b"<resources><plurals name='x'><item quantity='one' name='x'>x</item>"
            b"</plurals></resources>",
            "unsupported_structure",
        ),
        (
            b"<resources><string-array name='x'><item quantity='one'>x</item>"
            b"</string-array></resources>",
            "unsupported_structure",
        ),
        (b"<resources><string name='x'><em>x</em></string></resources>", "unsupported_structure"),
        (b"<resources><string name='x'><b class='x'>x</b></string></resources>", "unsupported_structure"),
        (
            b"<resources xmlns:x='urn:oasis:names:tc:xliff:document:1.2'>"
            b"<string name='x'><x:g>x</x:g></string></resources>",
            "unsupported_structure",
        ),
        (
            b"<resources xmlns:x='urn:oasis:names:tc:xliff:document:1.2'>"
            b"<string name='x'><x:g id=''>x</x:g></string></resources>",
            "unsupported_structure",
        ),
        (
            b"<resources xmlns:x='urn:oasis:names:tc:xliff:document:1.2'>"
            b"<string name='x'><x:g id='x' other='y'>x</x:g></string></resources>",
            "unsupported_structure",
        ),
        (
            b"<resources xmlns:x='urn:not-xliff'><string name='x'><x:g id='x'>x</x:g>"
            b"</string></resources>",
            "unsupported_structure",
        ),
        (b"<resources><?unsafe value?><string name='x'>x</string></resources>", "unsupported_structure"),
        (
            b"<resources><plurals name='x'><item quantity='one'>a</item>"
            b"<item quantity='one'>b</item></plurals></resources>",
            "duplicate_key",
        ),
    ),
)
def test_android_structured_markup_allowlist_is_exact(
    content: bytes,
    expected_code: str,
) -> None:
    _, registry = _canonical_modules()

    result = registry.parse_canonical_snapshot(_input(content=content))

    assert result.values == ()
    assert tuple(issue.code for issue in result.issues) == (expected_code,)


def test_android_escape_structure_retains_raw_text_while_display_is_decoded() -> None:
    _, registry = _canonical_modules()

    result = registry.parse_canonical_snapshot(
        _input(content=b"<resources><string name='escaped'>a\\nb\\t\\u263A\\\\c</string></resources>")
    )

    assert result.issues == ()
    value = result.values[0]
    assert value.display_text == "a\nb\t☺\\c"
    assert value.structure[-1].fields == (("value", r"a\nb\t\u263A\\c"),)
