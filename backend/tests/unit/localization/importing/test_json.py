"""Golden contracts for the strict canonical JSON localization adapter."""

from __future__ import annotations

import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization" / "json"


def _modules() -> tuple[Any, Any]:
    core = importlib.import_module("verboflex.localization.importing.core")
    try:
        adapter = importlib.import_module("verboflex.localization.importing.json")
    except ModuleNotFoundError:
        pytest.fail("canonical JSON adapter is not implemented")
    return core, adapter


def _input(content: bytes | None = None, **overrides: object) -> object:
    core = importlib.import_module("verboflex.localization.importing.core")
    fields: dict[str, object] = {
        "format": "json",
        "repository_side": "direct",
        "path": "locales.json",
        "content": content
        if content is not None
        else (_FIXTURES / "valid_nested.json").read_bytes(),
        "layout_identity": "json:locale-rooted:locales.json",
        "layout_version": 1,
        "base_language": "en",
    }
    fields.update(overrides)
    return core.CanonicalParserInput(**fields)


def _projection(result: object) -> dict[str, object]:
    entries = [
        {
            "display_text": value.display_text,
            "language": value.language,
            "logical_key": value.logical_key,
            "selector": value.selector.to_mapping(),
            "source_text": value.source_text,
            "translated_text": value.translated_text,
        }
        for value in result.values  # type: ignore[attr-defined]
    ]
    entries.sort(
        key=lambda entry: (
            str(entry["language"]),
            str(entry["logical_key"]),
            json.dumps(entry["selector"], sort_keys=True),
        )
    )
    return {"entries": entries, "format": "json"}


def test_json_nested_locale_rooted_golden_manifest() -> None:
    core, adapter = _modules()
    expected = json.loads((_FIXTURES / "valid_nested.expected.json").read_text())

    result = adapter.parse_json_localization(_input())

    assert result.issues == ()
    assert _projection(result) == expected
    assert result.values == tuple(sorted(result.values, key=core.canonical_value_order))
    assert len(result.values) == 8


def test_json_nested_repeated_leaf_names_use_raw_key_and_parent_selector() -> None:
    core, adapter = _modules()

    result = adapter.parse_json_localization(_input())

    titles = [value for value in result.values if value.logical_key == "title"]
    assert len(titles) == 4
    assert {value.logical_key for value in titles} == {"title"}
    assert {value.selector for value in titles} == {
        core.CanonicalSelector(kind="json_path", fields=(("parents", ("checkout",)),)),
        core.CanonicalSelector(kind="json_path", fields=(("parents", ("profile",)),)),
    }
    literal = next(
        value
        for value in result.values
        if value.language == "en" and value.logical_key == "literal.dot[0]"
    )
    assert literal.selector == core.CanonicalSelector(
        kind="json_path",
        fields=(("parents", ()),),
    )


def test_json_flat_per_locale_recurses_and_retains_source_order_in_locators() -> None:
    _, adapter = _modules()
    content = b'{"second":{"leaf":"two"},"first":{"leaf":"one"},"escaped\\u002ekey":"line\\nvalue"}'

    result = adapter.parse_json_localization(
        _input(
            content,
            repository_side="translations",
            path="assets/it_IT/messages.json",
            layout_identity="json:flat-per-locale:assets/{locale}/messages.json",
        )
    )

    assert result.issues == ()
    by_position = sorted(result.values, key=lambda value: value.locator.position)
    assert [value.display_text for value in by_position] == ["two", "one", "line\nvalue"]
    assert [value.logical_key for value in by_position] == ["leaf", "leaf", "escaped.key"]
    assert [dict(value.selector.fields)["parents"] for value in by_position] == [
        ("second",),
        ("first",),
        (),
    ]
    assert [value.locator.structural_address for value in by_position] == [
        ("document", "second", 0, "leaf", 0),
        ("document", "first", 1, "leaf", 0),
        ("document", "escaped.key", 2),
    ]
    assert {value.language for value in result.values} == {"it-IT"}
    assert all(value.source_text is None for value in result.values)


def test_json_empty_string_and_empty_object_are_distinct_with_base_authority() -> None:
    _, adapter = _modules()

    empty_string = adapter.parse_json_localization(
        _input(
            b'{"empty":""}',
            path="en.json",
            layout_identity="json:flat-per-locale:{locale}.json",
        )
    )
    empty_object = adapter.parse_json_localization(
        _input(
            b"{}",
            path="en.json",
            layout_identity="json:flat-per-locale:{locale}.json",
        )
    )
    missing_base = adapter.parse_json_localization(
        _input(
            b"{}",
            path="en.json",
            layout_identity="json:flat-per-locale:{locale}.json",
            base_language="",
        )
    )

    assert len(empty_string.values) == 1
    assert empty_string.values[0].display_text == ""
    assert empty_string.issues == ()
    assert empty_object.values == empty_object.issues == ()
    assert missing_base.values == ()
    assert tuple(issue.code for issue in missing_base.issues) == ("base_language_required",)


@pytest.mark.parametrize(
    "content",
    (
        b'{"bad":[]}',
        b'{"bad":1}',
        b'{"bad":true}',
        b'{"bad":null}',
    ),
)
def test_json_nested_unsupported_leaf_types_fail_without_partial_values(content: bytes) -> None:
    _, adapter = _modules()

    result = adapter.parse_json_localization(
        _input(
            b'{"good":"kept nowhere","nested":' + content[7:-1] + b"}",
            path="en.json",
            layout_identity="json:flat-per-locale:{locale}.json",
        )
    )

    assert result.values == ()
    assert tuple(issue.code for issue in result.issues) == ("unsupported_structure",)


def _invalid_case_content(case: dict[str, object]) -> bytes:
    content = case.get("content")
    if isinstance(content, str):
        return content.encode()
    content_hex = case.get("content_hex")
    assert isinstance(content_hex, str)
    return bytes.fromhex(content_hex)


def _flat_input(content: bytes, *, index: int = 0) -> object:
    return _input(
        content,
        path=f"assets/en/file-{index}.json",
        layout_identity=f"json:flat-per-locale:assets/{{locale}}/file-{index}.json",
    )


def _rooted_input(content: bytes, *, index: int = 0) -> object:
    path = f"catalog-{index}.json"
    return _input(
        content,
        path=path,
        layout_identity=f"json:locale-rooted:{path}",
    )


def _padded_flat(size: int, *, index: int = 0) -> bytes:
    document = f'{{"key-{index}":"value"}}'.encode()
    assert len(document) <= size
    return document + (b" " * (size - len(document)))


def _nested_document(depth: int) -> bytes:
    value = '"value"'
    for index in reversed(range(depth)):
        value = f'{{"level-{index}":{value}}}'
    return value.encode()


def _wide_document(count: int, *, objects: bool = False) -> bytes:
    value = "{}" if objects else '"value"'
    return ("{" + ",".join(f'"key-{index}":{value}' for index in range(count)) + "}").encode()


def test_json_hostile_fixture_inventory_fails_atomically_and_source_free() -> None:
    _, adapter = _modules()
    cases = json.loads((_FIXTURES / "invalid_cases.json").read_text())

    for case in cases:
        content = _invalid_case_content(case)
        parser_input = _flat_input(content) if case["layout"] == "flat" else _rooted_input(content)
        result = adapter.parse_json_localization(parser_input)

        assert result.values == (), case["id"]
        assert tuple(issue.code for issue in result.issues) == (case["expected_code"],), case["id"]
        assert len(result.issues) <= 5
        assert all(len(issue.message) <= 256 for issue in result.issues)
        assert all("secret" not in issue.message for issue in result.issues)
        assert all("<" not in issue.message for issue in result.issues)
        assert set(result.issues[0].to_mapping()) == {
            "code",
            "column",
            "line",
            "message",
            "path",
            "repository_side",
        }


def test_json_file_member_value_and_depth_limits_are_exact() -> None:
    _, adapter = _modules()

    exact_file = adapter.parse_json_localization(
        _flat_input(_padded_flat(adapter.MAX_CANONICAL_FILE_BYTES))
    )
    over_file = adapter.parse_json_localization(
        _flat_input(_padded_flat(adapter.MAX_CANONICAL_FILE_BYTES + 1))
    )
    exact_members = adapter.parse_json_localization(
        _flat_input(_wide_document(adapter.MAX_JSON_MEMBERS, objects=True))
    )
    over_members = adapter.parse_json_localization(
        _flat_input(_wide_document(adapter.MAX_JSON_MEMBERS + 1, objects=True))
    )
    exact_values = adapter.parse_json_localization(
        _flat_input(_wide_document(adapter.MAX_JSON_VALUES))
    )
    over_values = adapter.parse_json_localization(
        _flat_input(_wide_document(adapter.MAX_JSON_VALUES + 1))
    )
    exact_depth = adapter.parse_json_localization(
        _flat_input(_nested_document(adapter.MAX_JSON_DEPTH))
    )
    over_depth = adapter.parse_json_localization(
        _flat_input(_nested_document(adapter.MAX_JSON_DEPTH + 1))
    )

    assert len(exact_file.values) == 1
    assert over_file.values == () and over_file.issues
    assert exact_members.values == exact_members.issues == ()
    assert over_members.values == () and over_members.issues
    assert len(exact_values.values) == adapter.MAX_JSON_VALUES
    assert over_values.values == () and over_values.issues
    assert len(exact_depth.values) == 1
    assert over_depth.values == () and over_depth.issues


def test_json_peer_files_fail_atomically_and_obey_file_and_aggregate_limits() -> None:
    _, adapter = _modules()
    exact_files = tuple(
        cast(Any, _flat_input(f'{{"key-{index}":"value"}}'.encode(), index=index))
        for index in range(adapter.MAX_JSON_FILES)
    )
    exact_file_result = adapter.parse_json_localization_files(exact_files)
    over_file_result = adapter.parse_json_localization_files(
        exact_files
        + (
            cast(
                Any,
                _flat_input(b'{"over":"value"}', index=adapter.MAX_JSON_FILES),
            ),
        )
    )

    file_count = 21
    per_file, remainder = divmod(adapter.MAX_JSON_AGGREGATE_BYTES, file_count)
    exact_aggregate = tuple(
        cast(
            Any,
            _flat_input(
                _padded_flat(per_file + (1 if index < remainder else 0), index=index),
                index=index,
            ),
        )
        for index in range(file_count)
    )
    exact_aggregate_result = adapter.parse_json_localization_files(exact_aggregate)
    one_byte_over = replace(
        exact_aggregate[-1],
        content=exact_aggregate[-1].content + b" ",
    )
    over_aggregate_result = adapter.parse_json_localization_files(
        exact_aggregate[:-1] + (one_byte_over,)
    )
    bad = cast(Any, _flat_input(b'{"bad":null}', index=700))
    atomic = adapter.parse_json_localization_files((exact_files[0], bad))

    assert len(exact_file_result.values) == adapter.MAX_JSON_FILES
    assert over_file_result.values == () and over_file_result.issues
    assert len(exact_aggregate_result.values) == file_count
    assert over_aggregate_result.values == () and over_aggregate_result.issues
    assert atomic.values == ()
    assert tuple(issue.path for issue in atomic.issues) == ("assets/en/file-700.json",)


def test_json_concurrent_calls_are_byte_equal_and_failure_isolated() -> None:
    _, adapter = _modules()
    valid_input = _input()
    invalid_input = _flat_input(b'{"safe":"discarded","bad":null}')

    def parse(index: int) -> bytes:
        parser_input = valid_input if index % 2 == 0 else invalid_input
        result = adapter.parse_json_localization(parser_input)
        return json.dumps(result.to_mapping(), sort_keys=True, separators=(",", ":")).encode()

    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = tuple(executor.map(parse, range(64)))

    assert len(set(outputs[::2])) == 1
    assert len(set(outputs[1::2])) == 1
    assert json.loads(outputs[0])["values"]
    assert json.loads(outputs[1])["values"] == []
    after_failure = adapter.parse_json_localization(invalid_input)
    assert after_failure.values == ()
    assert tuple(issue.code for issue in after_failure.issues) == ("unsupported_structure",)


def test_json_valid_unicode_escapes_and_astral_pairs_decode_canonically() -> None:
    _, adapter = _modules()
    result = adapter.parse_json_localization(
        _flat_input(
            b'{"caf\\u00e9":"d\\u00e9j\\u00e0",'
            b'"emoji":"\\ud83d\\udc69\\ud83c\\udffd\\u200d\\ud83d\\udcbb"}'
        )
    )

    assert result.issues == ()
    assert {(value.logical_key, value.display_text) for value in result.values} == {
        ("caf\u00e9", "d\u00e9j\u00e0"),
        ("emoji", "\U0001f469\U0001f3fd\u200d\U0001f4bb"),
    }


def test_json_manifest_covers_required_categories_and_exact_limits() -> None:
    manifest = json.loads((_FIXTURES / "manifest.json").read_text())

    assert set(manifest["categories"]) == {
        "valid",
        "empty",
        "malformed",
        "escaped",
        "unicode",
        "nested",
        "duplicate",
        "encoding",
        "boundary",
        "non_string",
        "concurrency",
    }
    assert manifest["limits"] == {
        "file_bytes": 1_048_576,
        "aggregate_bytes": 20_971_520,
        "files": 500,
        "members": 5_000,
        "values": 5_000,
        "depth": 12,
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
def test_arbitrary_json_bytes_never_escape_or_return_partial_values(payload: bytes) -> None:
    _, adapter = _modules()

    result = adapter.parse_json_localization(_flat_input(payload))

    assert not (result.values and result.issues)
    assert len(result.issues) <= 5
    assert all(len(issue.message) <= 256 for issue in result.issues)
