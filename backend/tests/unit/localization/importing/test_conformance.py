"""Cross-format conformance for complete canonical localization parsing."""

from __future__ import annotations

import json
from dataclasses import fields, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast, get_args

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verboflex.localization.importing import core, registry

_FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization"
_MANIFEST = json.loads((_FIXTURES / "conformance" / "manifest.json").read_text())
_ROADMAP_CATEGORIES = {"valid", "empty", "malformed", "escaped", "unicode", "boundary"}
_LIMITS = {
    "file_bytes": 1_048_576,
    "aggregate_bytes": 20_971_520,
    "files": 500,
    "values": 5_000,
    "depth": 12,
    "issues": 5,
    "issue_message": 256,
    "path": 4_096,
    "coordinate": 2_147_483_647,
}
_FORMAT_CATEGORIES = {
    "android_xml": {
        "valid",
        "empty",
        "malformed",
        "escaped",
        "unicode",
        "markup",
        "plural",
        "array",
        "boundary",
    },
    "qt_ts": {
        "valid",
        "empty",
        "malformed",
        "escaped",
        "unicode",
        "markup",
        "numerus",
        "variant",
        "status",
        "duplicate",
        "encoding",
        "boundary",
        "concurrency",
    },
    "json": {
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
    },
    "ios_strings": {
        "valid",
        "empty",
        "malformed",
        "escaped",
        "unicode",
        "comments",
        "duplicate",
        "encoding",
        "boundary",
        "unsupported",
        "concurrency",
    },
}
_CONSTRUCTS = {
    format_name: {
        inventory_name: tuple(format_manifest[inventory_name])
        for inventory_name in ("supported_constructs", "rejected_constructs")
    }
    for format_name, format_manifest in _MANIFEST["formats"].items()
}


def _input(format_name: str, *, content: bytes | None = None, **overrides: object) -> Any:
    definitions: dict[str, dict[str, object]] = {
        "android_xml": {
            "repository_side": "direct",
            "path": "app/src/main/res/values/strings.xml",
            "content": (_FIXTURES / "android" / "scalar.xml").read_bytes(),
            "layout_identity": "app/src/main/res",
            "base_language": "en_US",
        },
        "qt_ts": {
            "repository_side": "direct",
            "path": "translations/app_it-IT.ts",
            "content": (_FIXTURES / "qt" / "valid_structured.ts").read_bytes(),
            "layout_identity": "qt-ts:translations/app_{locale}.ts",
            "base_language": "en_US",
        },
        "json": {
            "repository_side": "direct",
            "path": "locales.json",
            "content": (_FIXTURES / "json" / "valid_nested.json").read_bytes(),
            "layout_identity": "json:locale-rooted:locales.json",
            "base_language": "en",
        },
        "ios_strings": {
            "repository_side": "translations",
            "path": "mobile/it_IT.lproj/Localizable.strings",
            "content": (_FIXTURES / "ios" / "valid.strings").read_bytes(),
            "layout_identity": "ios-strings:mobile/{locale}.lproj/Localizable.strings",
            "base_language": "en",
        },
    }
    values = {"format": format_name, "layout_version": 1, **definitions[format_name]}
    if content is not None:
        values["content"] = content
    values.update(overrides)
    return core.CanonicalParserInput(**cast(Any, values))


def _canonical_bytes(result: core.CanonicalParseResult) -> bytes:
    return json.dumps(
        result.to_mapping(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _fixture_inputs(document: dict[str, object]) -> tuple[core.CanonicalParserInput, ...]:
    format_name = cast(str, document["format"])
    return tuple(
        core.CanonicalParserInput(
            format=cast(Any, format_name),
            repository_side=cast(Any, item["repository_side"]),
            path=cast(str, item["path"]),
            content=cast(str, item["content"]).encode(),
            layout_identity=cast(str, item["layout_identity"]),
            layout_version=cast(int, item["layout_version"]),
            base_language=cast(str, item["base_language"]),
        )
        for item in cast(list[dict[str, object]], document["inputs"])
    )


def _mapping_projection(result: core.CanonicalParseResult) -> list[dict[str, object]]:
    projected = [
        {
            "repository_side": value.locator.repository_side,
            "logical_key": value.logical_key,
            "language": value.language,
            "source_text": value.source_text,
            "translated_text": value.translated_text,
        }
        for value in result.values
    ]
    return sorted(
        projected,
        key=lambda value: (
            str(value["repository_side"]),
            str(value["logical_key"]),
            str(value["language"]),
        ),
    )


def _manifest_categories(format_name: str) -> set[str]:
    manifest = json.loads(
        (
            _FIXTURES
            / format_name.replace("_xml", "").replace("_ts", "").replace("_strings", "")
            / "manifest.json"
        ).read_text()
    )
    categories = manifest["categories"]
    return set(categories if isinstance(categories, list) else categories)


def test_fixture_manifest_category_equality() -> None:
    assert _MANIFEST["schema_version"] == 1
    assert set(_MANIFEST["roadmap_categories"]) == _ROADMAP_CATEGORIES
    assert set(_MANIFEST["formats"]) == set(get_args(core.CanonicalFormat))
    assert _MANIFEST["limits"] == _LIMITS
    for format_name, expected_categories in _FORMAT_CATEGORIES.items():
        conformance_categories = set(_MANIFEST["formats"][format_name]["categories"])
        assert conformance_categories == expected_categories
        assert _manifest_categories(format_name) == expected_categories
        assert conformance_categories >= _ROADMAP_CATEGORIES


def test_supported_and_rejected_construct_ids_are_exact_unique_and_disjoint() -> None:
    expected = {
        format_name: {
            inventory_name: tuple(sorted(values)) for inventory_name, values in inventories.items()
        }
        for format_name, inventories in _CONSTRUCTS.items()
    }
    actual: dict[str, dict[str, tuple[str, ...]]] = {}
    for format_name, format_manifest in _MANIFEST["formats"].items():
        supported = tuple(format_manifest["supported_constructs"])
        rejected = tuple(format_manifest["rejected_constructs"])
        assert supported == tuple(sorted(set(supported)))
        assert rejected == tuple(sorted(set(rejected)))
        assert set(supported).isdisjoint(rejected)
        actual[format_name] = {
            "supported_constructs": supported,
            "rejected_constructs": rejected,
        }
    assert actual == expected


@pytest.mark.parametrize("format_name", tuple(get_args(core.CanonicalFormat)))
def test_registry_dispatches_every_confirmed_format_to_a_complete_result(format_name: str) -> None:
    result = registry.parse_canonical_snapshot(_input(format_name))

    assert type(result) is core.CanonicalParseResult
    assert result.issues == ()
    assert result.values
    assert all(value.locator.format == format_name for value in result.values)
    assert all(
        value.locator.repository_side == _input(format_name).repository_side
        for value in result.values
    )


@pytest.mark.parametrize("format_name", tuple(get_args(core.CanonicalFormat)))
def test_canonical_result_bytes_are_stable_for_every_adapter(format_name: str) -> None:
    parser_input = _input(format_name)
    first = registry.parse_canonical_snapshot(parser_input)
    second = registry.parse_canonical_snapshot(parser_input)

    assert _canonical_bytes(first) == _canonical_bytes(second)
    assert _canonical_bytes(first) == _canonical_bytes(
        core.CanonicalParseResult(
            values=tuple(sorted(first.values, key=core.canonical_value_order))
        )
    )


@pytest.mark.parametrize(
    ("format_name", "content"),
    (
        ("android_xml", b"<resources><font>bad</font></resources>"),
        (
            "qt_ts",
            b'<TS version="2.1" language="it_IT"><context><name>x</name>'
            b'<message id="x"><source>x</source><translation><byte value="1"/>'
            b"</translation></message></context></TS>",
        ),
        ("json", b'{"key":42}'),
        ("ios_strings", b'key = "value";'),
    ),
)
def test_unlisted_or_rejected_constructs_fail_the_whole_snapshot(
    format_name: str, content: bytes
) -> None:
    result = registry.parse_canonical_snapshot(_input(format_name, content=content))

    assert result.values == ()
    assert len(result.issues) == 1
    assert result.issues[0].code in {
        "ambiguous_structure",
        "malformed_file",
        "unsupported_structure",
    }


@pytest.mark.parametrize(
    ("claimed_format", "actual_format"),
    (
        ("android_xml", "json"),
        ("qt_ts", "ios_strings"),
        ("json", "android_xml"),
        ("ios_strings", "qt_ts"),
    ),
)
def test_registry_rejects_cross_format_content_claims(
    claimed_format: str, actual_format: str
) -> None:
    claimed = _input(claimed_format)
    actual = _input(actual_format)
    result = registry.parse_canonical_snapshot(_input(claimed_format, content=actual.content))

    assert result.values == ()
    assert result.issues
    assert all(issue.path == claimed.path for issue in result.issues)


def test_shared_exact_resource_limits_match_every_adapter_manifest() -> None:
    from verboflex.localization.importing import (
        android_xml,
        ios_strings,
        qt_ts,
    )
    from verboflex.localization.importing import (
        json as json_adapter,
    )

    assert _LIMITS["file_bytes"] == core.MAX_CANONICAL_FILE_BYTES
    assert _LIMITS["aggregate_bytes"] == core.MAX_CANONICAL_AGGREGATE_BYTES
    assert _LIMITS["files"] == core.MAX_CANONICAL_FILES
    assert _LIMITS["values"] == core.MAX_CANONICAL_VALUES
    assert _LIMITS["depth"] == core.MAX_CANONICAL_DEPTH
    assert _LIMITS["issues"] == core.MAX_CANONICAL_ISSUES
    assert _LIMITS["issue_message"] == core.MAX_CANONICAL_ISSUE_MESSAGE_LENGTH
    assert _LIMITS["path"] == core.MAX_CANONICAL_PATH_LENGTH
    assert _LIMITS["coordinate"] == core.MAX_CANONICAL_COORDINATE
    for adapter in (android_xml, qt_ts, json_adapter, ios_strings):
        assert adapter.MAX_CANONICAL_FILE_BYTES == core.MAX_CANONICAL_FILE_BYTES
    for format_name in get_args(core.CanonicalFormat):
        manifest = json.loads(
            (
                _FIXTURES
                / format_name.replace("_xml", "").replace("_ts", "").replace("_strings", "")
                / "manifest.json"
            ).read_text()
        )
        assert manifest["limits"]["file_bytes"] == _LIMITS["file_bytes"]
        assert manifest["limits"]["aggregate_bytes"] == _LIMITS["aggregate_bytes"]
        assert manifest["limits"]["files"] == _LIMITS["files"]
        assert manifest["limits"]["issues"] == _LIMITS["issues"]


def test_registry_closes_adapter_exceptions_and_invalid_result_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser_input = _input("android_xml")

    def raises_secret(_: core.CanonicalParserInput) -> core.CanonicalParseResult:
        raise RuntimeError("repository source secret")

    monkeypatch.setattr(
        registry,
        "_ADAPTERS",
        MappingProxyType({**registry._ADAPTERS, "android_xml": raises_secret}),
    )
    raised = registry.parse_canonical_snapshot(parser_input)
    assert raised.values == ()
    assert raised.issues[0].to_mapping() == {
        "code": "malformed_file",
        "column": None,
        "line": None,
        "message": "Canonical parser input is invalid.",
        "path": parser_input.path,
        "repository_side": "direct",
    }
    assert "secret" not in _canonical_bytes(raised).decode()

    monkeypatch.setattr(
        registry,
        "_ADAPTERS",
        MappingProxyType({**registry._ADAPTERS, "android_xml": cast(Any, lambda _: object())}),
    )
    invalid = registry.parse_canonical_snapshot(parser_input)
    assert invalid.values == ()
    assert invalid.issues[0].code == "malformed_file"


def test_issue_payload_surface_remains_closed_and_bounded() -> None:
    assert {field.name for field in fields(core.CanonicalIssue)} == {
        "code",
        "repository_side",
        "path",
        "message",
        "line",
        "column",
    }
    assert set(get_args(core.IssueCode)) == {
        "malformed_file",
        "ambiguous_structure",
        "unsupported_structure",
        "duplicate_key",
        "base_language_required",
    }


@settings(max_examples=60, deadline=None)
@given(
    format_name=st.sampled_from(tuple(get_args(core.CanonicalFormat))),
    payload=st.binary(max_size=256),
)
def test_arbitrary_cross_format_inputs_return_only_validated_bounded_results(
    format_name: str, payload: bytes
) -> None:
    result = registry.parse_canonical_snapshot(_input(format_name, content=payload))

    assert type(result) is core.CanonicalParseResult
    assert not (result.values and result.issues)
    assert len(result.values) <= core.MAX_CANONICAL_VALUES
    assert len(result.issues) <= core.MAX_CANONICAL_ISSUES
    assert all(type(value) is core.CanonicalValue for value in result.values)
    assert all(type(issue) is core.CanonicalIssue for issue in result.issues)
    serialized = _canonical_bytes(result).decode("utf-8")
    assert "Traceback" not in serialized
    assert "Exception" not in serialized


def test_direct_mapping_matches_hand_authored_fixture_and_is_order_stable() -> None:
    fixture = json.loads((_FIXTURES / "conformance" / "direct.json").read_text())
    inputs = _fixture_inputs(fixture)

    result = registry.parse_canonical_mapping(inputs)

    assert result.issues == ()
    assert _mapping_projection(result) == sorted(
        fixture["expected"],
        key=lambda value: (
            value["repository_side"],
            value["logical_key"],
            value["language"],
        ),
    )
    assert _canonical_bytes(result) == _canonical_bytes(registry.parse_canonical_mapping(inputs))


@pytest.mark.parametrize("case_id", ("exact-join", "translation-only", "key-only"))
def test_separate_mapping_joins_without_manufacturing_data(case_id: str) -> None:
    fixture = json.loads((_FIXTURES / "conformance" / "separate.json").read_text())
    case = next(item for item in fixture["cases"] if item["id"] == case_id)
    inputs = _fixture_inputs({"format": fixture["format"], "inputs": case["inputs"]})

    result = registry.parse_canonical_mapping(tuple(reversed(inputs)))

    assert result.issues == ()
    assert _mapping_projection(result) == sorted(
        case["expected"],
        key=lambda value: (
            value["repository_side"],
            value["logical_key"],
            value["language"],
        ),
    )
    assert _canonical_bytes(result) == _canonical_bytes(registry.parse_canonical_mapping(inputs))


@pytest.mark.parametrize(
    "case_id",
    (
        "duplicate-path",
        "incompatible-selector",
        "one-side-failure",
        "ambiguous-language",
    ),
)
def test_separate_mapping_failures_are_atomic(case_id: str) -> None:
    fixture = json.loads((_FIXTURES / "conformance" / "separate.json").read_text())
    case = next(item for item in fixture["cases"] if item["id"] == case_id)
    inputs = _fixture_inputs({"format": fixture["format"], "inputs": case["inputs"]})

    result = registry.parse_canonical_mapping(inputs)

    assert result.values == ()
    assert result.issues
    assert result.issues[0].code == case["expected_issue"]


def test_mapping_rejects_zero_files_incomplete_sides_and_mixed_topologies() -> None:
    assert registry.parse_canonical_mapping(()).issues[0].code == "malformed_file"
    keys_only = _input(
        "json",
        repository_side="keys",
        path="keys/en/messages.json",
        content=b"{}",
        layout_identity="json:flat-per-locale:keys/{locale}/messages.json",
    )
    direct = _input("json", content=b"{}")

    incomplete = registry.parse_canonical_mapping((keys_only,))
    mixed = registry.parse_canonical_mapping((direct, keys_only))

    assert incomplete.values == ()
    assert incomplete.issues[0].code == "ambiguous_structure"
    assert mixed.values == ()
    assert mixed.issues[0].code == "ambiguous_structure"


def test_separate_issue_order_is_keys_then_translations_and_provider_path() -> None:
    inputs = (
        _input(
            "json",
            repository_side="translations",
            path="translations/it/z.json",
            content=b"{",
            layout_identity="json:flat-per-locale:translations/{locale}/z.json",
        ),
        _input(
            "json",
            repository_side="keys",
            path="keys/en/z.json",
            content=b"{",
            layout_identity="json:flat-per-locale:keys/{locale}/z.json",
        ),
        _input(
            "json",
            repository_side="translations",
            path="translations/it/a.json",
            content=b"{",
            layout_identity="json:flat-per-locale:translations/{locale}/a.json",
        ),
        _input(
            "json",
            repository_side="keys",
            path="keys/en/a.json",
            content=b"{",
            layout_identity="json:flat-per-locale:keys/{locale}/a.json",
        ),
    )

    result = registry.parse_canonical_mapping(inputs)

    assert result.values == ()
    assert [(issue.repository_side, issue.path) for issue in result.issues] == [
        ("keys", "keys/en/a.json"),
        ("keys", "keys/en/z.json"),
        ("translations", "translations/it/a.json"),
        ("translations", "translations/it/z.json"),
    ]


def test_mapping_rejects_duplicate_identity_and_overlapping_provider_paths() -> None:
    first = _input(
        "json",
        repository_side="direct",
        path="assets/en/first.json",
        content=b'{"same":"one"}',
        layout_identity="json:flat-per-locale:assets/{locale}/first.json",
    )
    duplicate_identity = _input(
        "json",
        repository_side="direct",
        path="assets/en/second.json",
        content=b'{"same":"two"}',
        layout_identity="json:flat-per-locale:assets/{locale}/second.json",
    )
    overlapping_path = replace(first, content=b'{"other":"two"}')

    for inputs in ((first, duplicate_identity), (first, overlapping_path)):
        result = registry.parse_canonical_mapping(inputs)
        assert result.values == ()
        assert result.issues[0].code == "duplicate_key"


def test_mapping_file_and_aggregate_limits_are_exact() -> None:
    file_inputs = tuple(
        _input(
            "json",
            repository_side="direct",
            path=f"assets/en/messages-{index}.json",
            content=b"{}",
            layout_identity=f"json:flat-per-locale:assets/{{locale}}/messages-{index}.json",
        )
        for index in range(core.MAX_CANONICAL_FILES)
    )
    assert registry.parse_canonical_mapping(file_inputs).issues == ()
    assert (
        registry.parse_canonical_mapping(
            (*file_inputs, replace(file_inputs[-1], path="assets/en/overflow.json"))
        )
        .issues[0]
        .code
        == "unsupported_structure"
    )

    exact_content = b"{}" + b" " * (core.MAX_CANONICAL_FILE_BYTES - 2)
    aggregate_inputs = tuple(
        _input(
            "json",
            repository_side="direct",
            path=f"assets/en/aggregate-{index}.json",
            content=exact_content,
            layout_identity=f"json:flat-per-locale:assets/{{locale}}/aggregate-{index}.json",
        )
        for index in range(core.MAX_CANONICAL_AGGREGATE_BYTES // core.MAX_CANONICAL_FILE_BYTES)
    )
    assert registry.parse_canonical_mapping(aggregate_inputs).issues == ()
    one_over = _input(
        "json",
        repository_side="direct",
        path="assets/en/one-over.json",
        content=b" ",
        layout_identity="json:flat-per-locale:assets/{locale}/one-over.json",
    )
    assert (
        registry.parse_canonical_mapping((*aggregate_inputs, one_over)).issues[0].code
        == "unsupported_structure"
    )


def test_mapping_value_order_uses_side_path_position_key_language_and_selector_bytes() -> None:
    first = _input(
        "json",
        repository_side="direct",
        path="assets/en/a.json",
        content=b'{"z":"last","a":"first"}',
        layout_identity="json:flat-per-locale:assets/{locale}/a.json",
    )
    second = _input(
        "json",
        repository_side="direct",
        path="assets/it/b.json",
        content=b'{"a":"second"}',
        layout_identity="json:flat-per-locale:assets/{locale}/b.json",
    )

    result = registry.parse_canonical_mapping((second, first))

    assert result.issues == ()
    assert [
        (value.locator.path, value.locator.position, value.logical_key, value.language)
        for value in result.values
    ] == [
        ("assets/en/a.json", 0, "z", "en"),
        ("assets/en/a.json", 1, "a", "en"),
        ("assets/it/b.json", 0, "a", "it"),
    ]
