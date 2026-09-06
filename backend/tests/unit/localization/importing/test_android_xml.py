"""Canonical Android XML scalar adapter contracts."""

from __future__ import annotations

import importlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization" / "android"


def _canonical_modules() -> tuple[Any, Any]:
    """Resolve production modules while making a missing adapter a behavioral RED."""
    try:
        core = importlib.import_module("verboflex.localization.importing.core")
        registry = importlib.import_module("verboflex.localization.importing.registry")
    except ModuleNotFoundError:
        pytest.fail("canonical Android adapter is not implemented")
    return core, registry


def _android_module() -> Any:
    return importlib.import_module("verboflex.localization.importing.android_xml")


@pytest.mark.parametrize(
    "container,item",
    [("plurals", '<item quantity="other">A</item>'), ("string-array", "<item>A</item>")],
)
@pytest.mark.parametrize("tail", ["LOST", "\n LOST \t"])
def test_android_structured_item_tail_cannot_silently_discard_content(container, item, tail):
    _, registry = _canonical_modules()
    content = (
        '<resources><string name="peer">Peer</string>'
        f'<{container} name="items">{item}{tail}</{container}></resources>'
    ).encode()
    result = registry.parse_canonical_snapshot(_input(content=content))
    assert result.values == ()
    assert [issue.code for issue in result.issues] == ["unsupported_structure"]


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
            b"<resources><string name='key'><font>value</font></string></resources>",
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
        "markup",
        "files",
        "files",
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
    assert (
        core.CanonicalStructureNode(
            kind="android_xml:inline",
            fields=(
                ("event", "start"),
                ("name", "g"),
                ("namespace", "urn:oasis:names:tc:xliff:document:1.2"),
                ("id", "count"),
                ("example", "2"),
            ),
        )
        in markup.structure
    )


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
            b"<resources><plurals name='x'><item quantity='invalid'>x</item></plurals></resources>",
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
        (
            b"<resources><string name='x'><b class='x'>x</b></string></resources>",
            "unsupported_structure",
        ),
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
        (
            b"<resources><?unsafe value?><string name='x'>x</string></resources>",
            "unsupported_structure",
        ),
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

    content = b"<resources><string name='escaped'>a\\nb\\t\\u263A\\\\c</string></resources>"
    result = registry.parse_canonical_snapshot(_input(content=content))

    assert result.issues == ()
    value = result.values[0]
    assert value.display_text == "a\nb\t☺\\c"
    assert value.structure[-1].fields == (("value", r"a\nb\t\u263A\\c"),)


def _invalid_case_content(case: dict[str, object]) -> bytes:
    content = case.get("content")
    if isinstance(content, str):
        return content.encode()
    content_hex = case.get("content_hex")
    assert isinstance(content_hex, str)
    return bytes.fromhex(content_hex)


def _padded_xml(size: int, *, key: str = "boundary") -> bytes:
    document = f"<resources><string name='{key}'>x</string></resources>".encode()
    assert len(document) <= size
    return document + (b" " * (size - len(document)))


def _array_xml(count: int) -> bytes:
    return (
        b"<resources><string-array name='values'>"
        + (b"<item>x</item>" * count)
        + b"</string-array></resources>"
    )


def _nested_xml(inline_depth: int) -> bytes:
    return (
        b"<resources><string name='depth'>"
        + (b"<b>" * inline_depth)
        + b"x"
        + (b"</b>" * inline_depth)
        + b"</string></resources>"
    )


def _structure_xml(extra_comments: int) -> bytes:
    inline_count = 1_364
    return (
        b"<resources><string name='structure'>"
        + (b"<b/>" * inline_count)
        + (b"<!--x-->" * extra_comments)
        + b"<![CDATA[x]]></string></resources>"
    )


def test_android_hostile_fixture_inventory_fails_closed_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, registry = _canonical_modules()
    cases = json.loads((_FIXTURES / "invalid_cases.json").read_text())
    attempted_network: list[object] = []

    def fail_external_request(*args: object, **kwargs: object) -> None:
        attempted_network.append((args, kwargs))
        raise AssertionError("XML parsing attempted an external request")

    monkeypatch.setattr("urllib.request.urlopen", fail_external_request)
    for case in cases:
        result = registry.parse_canonical_snapshot(_input(content=_invalid_case_content(case)))
        assert result.values == (), case["id"]
        assert tuple(issue.code for issue in result.issues) == (case["expected_code"],), case["id"]
        assert len(result.issues) <= 5
        assert all(len(issue.message) <= 256 for issue in result.issues)
        assert all("secret" not in issue.message for issue in result.issues)
        assert set(result.issues[0].to_mapping()) == {
            "code",
            "column",
            "line",
            "message",
            "path",
            "repository_side",
        }
    assert attempted_network == []


def test_android_empty_resources_and_empty_value_remain_distinct() -> None:
    _, registry = _canonical_modules()

    empty_file = registry.parse_canonical_snapshot(_input(content=b"<resources/>"))
    empty_value = registry.parse_canonical_snapshot(
        _input(content=b"<resources><string name='empty'></string></resources>")
    )

    assert empty_file.values == ()
    assert empty_file.issues == ()
    assert len(empty_value.values) == 1
    assert empty_value.values[0].display_text == ""
    assert empty_value.issues == ()


@pytest.mark.parametrize("raw", (None, {}, (), b"<resources/>"))
def test_android_missing_or_untyped_parser_input_is_rejected(raw: object) -> None:
    _, registry = _canonical_modules()

    result = registry.parse_canonical_snapshot(cast(Any, raw))

    assert result.values == ()
    assert tuple(issue.code for issue in result.issues) == ("malformed_file",)


def test_android_accepts_only_strict_utf8_with_optional_single_bom() -> None:
    _, registry = _canonical_modules()
    document = (
        b"<?xml version='1.0' encoding='uTf-8'?>"
        b"<resources><string name='unicode'>\xe2\x98\xba</string></resources>"
    )

    plain = registry.parse_canonical_snapshot(_input(content=document))
    with_bom = registry.parse_canonical_snapshot(_input(content=b"\xef\xbb\xbf" + document))

    assert plain.to_mapping() == with_bom.to_mapping()
    assert plain.values[0].display_text == "☺"


def test_android_decoded_key_and_selector_equality_is_exact() -> None:
    _, registry = _canonical_modules()
    content = (
        "<resources><string name='café'>one</string>"
        "<string name='cafe\u0301'>two</string></resources>"
    ).encode()

    result = registry.parse_canonical_snapshot(_input(content=content))

    assert result.issues == ()
    assert {value.logical_key for value in result.values} == {"café", "cafe\u0301"}


@pytest.mark.parametrize("dispatch", ["registry", "adapter"])
def test_android_file_byte_limit_accepts_exact_and_rejects_one_over(dispatch: str) -> None:
    android = _android_module()
    _, registry = _canonical_modules()

    parse = (
        registry.parse_canonical_snapshot if dispatch == "registry" else android.parse_android_xml
    )
    exact = parse(_input(content=_padded_xml(android.MAX_CANONICAL_FILE_BYTES)))
    over = parse(_input(content=_padded_xml(android.MAX_CANONICAL_FILE_BYTES + 1)))

    assert len(exact.values) == 1
    assert exact.issues == ()
    assert over.values == ()
    assert tuple(issue.code for issue in over.issues) == ("malformed_file",)


def test_android_value_limit_accepts_exact_and_rejects_one_over() -> None:
    android = _android_module()
    _, registry = _canonical_modules()

    exact = registry.parse_canonical_snapshot(
        _input(content=_array_xml(android.MAX_ANDROID_VALUES))
    )
    over = registry.parse_canonical_snapshot(
        _input(content=_array_xml(android.MAX_ANDROID_VALUES + 1))
    )

    assert len(exact.values) == android.MAX_ANDROID_VALUES
    assert exact.issues == ()
    assert over.values == ()
    assert tuple(issue.code for issue in over.issues) == ("unsupported_structure",)


def test_android_depth_limit_accepts_exact_and_rejects_one_over() -> None:
    android = _android_module()
    _, registry = _canonical_modules()
    inline_at_limit = android.MAX_ANDROID_XML_DEPTH - 2

    exact = registry.parse_canonical_snapshot(_input(content=_nested_xml(inline_at_limit)))
    over = registry.parse_canonical_snapshot(_input(content=_nested_xml(inline_at_limit + 1)))

    assert len(exact.values) == 1
    assert exact.issues == ()
    assert over.values == ()
    assert tuple(issue.code for issue in over.issues) == ("unsupported_structure",)


def test_android_structure_limit_accepts_exact_and_rejects_one_over() -> None:
    android = _android_module()
    _, registry = _canonical_modules()

    exact = registry.parse_canonical_snapshot(_input(content=_structure_xml(extra_comments=1)))
    over = registry.parse_canonical_snapshot(_input(content=_structure_xml(extra_comments=2)))

    assert len(exact.values[0].structure) == android.MAX_ANDROID_STRUCTURE_NODES
    assert exact.issues == ()
    assert over.values == ()
    assert tuple(issue.code for issue in over.issues) == ("unsupported_structure",)


def test_android_peer_files_fail_atomically_and_obey_aggregate_limits() -> None:
    android = _android_module()
    core, _ = _canonical_modules()
    good = cast(Any, _input(path="app/src/main/res/values/one.xml"))
    bad = cast(
        Any,
        _input(
            path="app/src/main/res/values/two.xml",
            content=b"<resources><string name='bad'>broken</resources>",
        ),
    )

    failed = android.parse_android_xml_files((good, bad))

    assert failed.values == ()
    assert tuple(issue.code for issue in failed.issues) == ("malformed_file",)
    assert failed.issues[0].path == "app/src/main/res/values/two.xml"

    invalid_peers = tuple(
        cast(
            Any,
            _input(
                path=f"app/src/main/res/values/invalid-{index}.xml",
                content=b"<resources>",
            ),
        )
        for index in range(6)
    )
    capped = android.parse_android_xml_files(invalid_peers)
    assert capped.values == ()
    assert len(capped.issues) == android.MAX_ANDROID_ISSUES
    assert tuple(issue.path for issue in capped.issues) == tuple(
        sorted(issue.path for issue in capped.issues)
    )

    exact_files = tuple(
        core.CanonicalParserInput(
            format="android_xml",
            repository_side="direct",
            path=f"app/src/main/res/values/file-{index}.xml",
            content=_padded_xml(41_943, key=f"key-{index}"),
            layout_identity="app/src/main/res",
            layout_version=1,
            base_language="en",
        )
        for index in range(android.MAX_ANDROID_FILES)
    )
    assert sum(len(item.content) for item in exact_files) <= android.MAX_ANDROID_AGGREGATE_BYTES
    assert len(android.parse_android_xml_files(exact_files).values) == android.MAX_ANDROID_FILES
    assert android.parse_android_xml_files(exact_files + (good,)).values == ()

    exact_aggregate = tuple(
        core.CanonicalParserInput(
            format="android_xml",
            repository_side="direct",
            path=f"app/src/main/res/values/aggregate-{index}.xml",
            content=_padded_xml(android.MAX_CANONICAL_FILE_BYTES, key=f"aggregate-{index}"),
            layout_identity="app/src/main/res",
            layout_version=1,
            base_language="en",
        )
        for index in range(android.MAX_ANDROID_AGGREGATE_BYTES // android.MAX_CANONICAL_FILE_BYTES)
    )
    assert sum(len(item.content) for item in exact_aggregate) == android.MAX_ANDROID_AGGREGATE_BYTES
    assert len(android.parse_android_xml_files(exact_aggregate).values) == len(exact_aggregate)
    one_byte_over = replace(exact_aggregate[-1], content=exact_aggregate[-1].content + b" ")
    assert android.parse_android_xml_files(exact_aggregate[:-1] + (one_byte_over,)).values == ()


def test_android_manifest_covers_required_categories_and_exact_limits() -> None:
    manifest = json.loads((_FIXTURES / "manifest.json").read_text())

    assert set(manifest["categories"]) == {
        "valid",
        "empty",
        "malformed",
        "escaped",
        "unicode",
        "markup",
        "plural",
        "array",
        "boundary",
    }
    assert manifest["limits"] == {
        "file_bytes": 1_048_576,
        "aggregate_bytes": 20_971_520,
        "files": 500,
        "values": 5_000,
        "depth": 12,
        "structure_nodes_per_value": 4_096,
        "issues": 5,
        "issue_message": 256,
        "path": 4_096,
        "coordinate": 2_147_483_647,
    }
    invalid_ids = [
        case["id"] for case in json.loads((_FIXTURES / "invalid_cases.json").read_text())
    ]
    assert len(invalid_ids) == len(set(invalid_ids))


@settings(max_examples=100, deadline=None)
@given(st.binary(max_size=4_096))
def test_arbitrary_android_bytes_never_escape_or_return_partial_values(payload: bytes) -> None:
    _, registry = _canonical_modules()

    result = registry.parse_canonical_snapshot(_input(content=payload))

    assert not (result.values and result.issues)
    assert len(result.issues) <= 5
    assert all(len(issue.message) <= 256 for issue in result.issues)
