"""Golden contracts for the strict canonical JSON localization adapter."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

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
    content = (
        b'{"second":{"leaf":"two"},"first":{"leaf":"one"},'
        b'"escaped\\u002ekey":"line\\nvalue"}'
    )

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
