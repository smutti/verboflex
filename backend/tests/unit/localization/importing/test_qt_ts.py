"""Golden contracts for the complete Qt TS canonical adapter."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

_FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization" / "qt"


def _modules() -> tuple[Any, Any]:
    core = importlib.import_module("verboflex.localization.importing.core")
    try:
        qt = importlib.import_module("verboflex.localization.importing.qt_ts")
    except ModuleNotFoundError:
        pytest.fail("canonical Qt TS adapter is not implemented")
    return core, qt


def _input(content: bytes | None = None, **overrides: object) -> object:
    core = importlib.import_module("verboflex.localization.importing.core")
    fields: dict[str, object] = {
        "format": "qt_ts",
        "repository_side": "direct",
        "path": "translations/app_it-IT.ts",
        "content": content
        if content is not None
        else (_FIXTURES / "valid_structured.ts").read_bytes(),
        "layout_identity": "qt-ts:translations/app_{locale}.ts",
        "layout_version": 1,
        "base_language": "en_US",
    }
    fields.update(overrides)
    return core.CanonicalParserInput(**fields)


def _node_fields(value: object, kind: str) -> list[dict[str, object]]:
    return [dict(node.fields) for node in value.structure if node.kind == kind]  # type: ignore[attr-defined]


def _golden_projection(result: object) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    document = _node_fields(result.values[0], "qt_ts:document")[0]  # type: ignore[attr-defined]
    for value in result.values:  # type: ignore[attr-defined]
        translation = _node_fields(value, "qt_ts:translation")[0]
        entries.append(
            {
                "deleted": translation["deleted"],
                "display_text": value.display_text,
                "locations": _node_fields(value, "qt_ts:location"),
                "logical_key": value.logical_key,
                "review_state": translation["review_state"],
                "selector": value.selector.to_mapping(),
                "source_text": value.source_text,
                "status": translation["status"],
                "translated_text": value.translated_text,
            }
        )
    entries.sort(
        key=lambda entry: json.dumps(entry["selector"], sort_keys=True) + str(entry["logical_key"])
    )
    entries.sort(key=lambda entry: str(entry["logical_key"]))
    return {
        "entries": entries,
        "format": "qt_ts",
        "language": document["language"],
        "source_language": document["source_language"],
        "version": document["version"],
    }


def test_qt_identity_numerus_variant_and_status_golden_manifest() -> None:
    core, qt = _modules()
    expected = json.loads((_FIXTURES / "valid_structured.expected.json").read_text())

    result = qt.parse_qt_ts(_input())

    assert result.issues == ()
    assert _golden_projection(result) == expected
    assert result.values == tuple(sorted(result.values, key=core.canonical_value_order))
    assert len(result.values) == 9


def test_qt_identity_metadata_and_locations_are_lossless_and_typed() -> None:
    core, qt = _modules()

    result = qt.parse_qt_ts(_input())

    id_value = next(
        value
        for value in result.values
        if value.logical_key == "checkout.pay"
        and dict(value.selector.fields)["identity_kind"] == "id"
    )
    assert id_value.selector == core.CanonicalSelector(
        kind="scalar",
        fields=(("identity_kind", "id"),),
    )
    assert _node_fields(id_value, "qt_ts:document") == [
        {"version": "2.1", "language": "it-IT", "source_language": "en-US"}
    ]
    assert _node_fields(id_value, "qt_ts:defaultcodec") == [{"value": "UTF-8"}]
    assert _node_fields(id_value, "qt_ts:dependency") == [
        {"catalog": "shared"},
        {},
    ]
    assert _node_fields(id_value, "qt_ts:context") == [{"name": "MainWindow"}]
    assert _node_fields(id_value, "qt_ts:comment") == [
        {"scope": "context", "value": "Checkout controls"},
        {"scope": "message", "value": "button"},
    ]
    assert _node_fields(id_value, "qt_ts:location") == [
        {"filename": "../src/main.cpp", "filename_explicit": True, "line": "12"},
        {"filename": "../src/main.cpp", "filename_explicit": False, "line": "+3"},
    ]
    assert id_value.source_text == "Pay <now>"
    assert id_value.translated_text == "Paga <ora>"
    assert id_value.locator.structural_address == ("TS", "context", 0, "message", 0)


def test_qt_identity_uses_id_or_source_without_synthesizing_context_into_the_key() -> None:
    core, qt = _modules()

    result = qt.parse_qt_ts(_input())

    same_raw_key = [value for value in result.values if value.logical_key == "checkout.pay"]
    assert len(same_raw_key) == 3
    assert {value.logical_key for value in same_raw_key} == {"checkout.pay"}
    assert {value.selector.kind for value in same_raw_key} == {"scalar"}
    assert {core.canonical_selector_digest(value.selector) for value in same_raw_key} == {
        core.canonical_selector_digest(
            core.CanonicalSelector(kind="scalar", fields=(("identity_kind", "id"),))
        ),
        core.canonical_selector_digest(
            core.CanonicalSelector(
                kind="scalar",
                fields=(("identity_kind", "source"), ("context", "MainWindow")),
            )
        ),
        core.canonical_selector_digest(
            core.CanonicalSelector(
                kind="scalar",
                fields=(
                    ("identity_kind", "source"),
                    ("context", "Secondary"),
                    ("disambiguation", "secondary"),
                ),
            )
        ),
    }


def test_qt_numerus_and_nested_variant_siblings_are_individually_addressable() -> None:
    _, qt = _modules()

    result = qt.parse_qt_ts(_input())

    numerus = [value for value in result.values if value.logical_key == "cart.items"]
    nested = [value for value in result.values if value.logical_key == "nested.items"]
    assert [
        (value.selector.kind, dict(value.selector.fields)["form_index"]) for value in numerus
    ] == [
        ("qt_numerus", 0),
        ("qt_numerus", 1),
    ]
    assert {
        (
            value.selector.kind,
            dict(value.selector.fields)["form_index"],
            dict(value.selector.fields)["priority"],
        )
        for value in nested
    } == {
        ("qt_length_variant", 0, 1),
        ("qt_length_variant", 0, 2),
    }


def test_qt_status_is_always_draft_and_obsolete_or_vanished_is_deleted() -> None:
    _, qt = _modules()

    result = qt.parse_qt_ts(_input())

    translations = [_node_fields(value, "qt_ts:translation")[0] for value in result.values]
    assert {translation["review_state"] for translation in translations} == {"draft"}
    assert "approved" not in {translation["review_state"] for translation in translations}
    assert {(translation["status"], translation["deleted"]) for translation in translations} >= {
        ("active", False),
        ("unfinished", False),
        ("obsolete", True),
        ("vanished", True),
    }


def test_qt_identity_ignores_mutable_qt_locations() -> None:
    core, qt = _modules()
    original = (
        b"<TS version='2.1' language='it'><context><name>Main</name><message id='stable'>"
        b"<location filename='old.cpp' line='1'/><source>Hello</source>"
        b"<translation>Ciao</translation></message></context></TS>"
    )
    moved = original.replace(b"old.cpp", b"new.cpp").replace(b"line='1'", b"line='99'")

    first = qt.parse_qt_ts(_input(original, path="translations/app_it.ts"))
    second = qt.parse_qt_ts(_input(moved, path="translations/app_it.ts"))

    assert first.issues == second.issues == ()
    assert (
        first.values[0].logical_key,
        first.values[0].language,
        core.canonical_selector_digest(first.values[0].selector),
    ) == (
        second.values[0].logical_key,
        second.values[0].language,
        core.canonical_selector_digest(second.values[0].selector),
    )
    assert _node_fields(first.values[0], "qt_ts:location") != _node_fields(
        second.values[0], "qt_ts:location"
    )


def test_qt_identity_accepts_ts_20_and_normalizes_languages() -> None:
    _, qt = _modules()
    content = (
        b"<TS version='2.0' language='sr_Latn_RS' sourcelanguage='en_US'>"
        b"<context><name>Main</name><message><source>Hello</source>"
        b"<translation>Zdravo</translation></message></context></TS>"
    )

    result = qt.parse_qt_ts(
        _input(
            content,
            path="translations/app_sr-Latn-RS.ts",
            layout_identity="qt-ts:translations/app_{locale}.ts",
        )
    )

    assert result.issues == ()
    assert result.values[0].language == "sr-Latn-RS"
    assert _node_fields(result.values[0], "qt_ts:document") == [
        {"version": "2.0", "language": "sr-Latn-RS", "source_language": "en-US"}
    ]
