"""Golden contracts for the complete Qt TS canonical adapter."""

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

    def entry_order(entry: dict[str, object]) -> tuple[str, bool, str, str]:
        selector: Any = entry["selector"]
        return (
            str(entry["logical_key"]),
            selector["fields"]["identity_kind"] != "id",
            selector["kind"],
            json.dumps(selector["fields"], sort_keys=True),
        )

    entries.sort(key=entry_order)
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


def _invalid_case_content(case: dict[str, object]) -> bytes:
    content = case.get("content")
    if isinstance(content, str):
        return content.encode()
    content_hex = case.get("content_hex")
    assert isinstance(content_hex, str)
    return bytes.fromhex(content_hex)


def _message(identifier: str, *, translation: str = "x") -> bytes:
    return (
        f"<message id='{identifier}'><source>x</source>"
        f"<translation>{translation}</translation></message>"
    ).encode()


def _document(messages: bytes = b"", *, language: str = "it-IT") -> bytes:
    return (
        f"<TS version='2.1' language='{language}'><context><name>Main</name>".encode()
        + messages
        + b"</context></TS>"
    )


def _padded_document(size: int, *, identifier: str = "boundary") -> bytes:
    document = _document(_message(identifier))
    assert len(document) <= size
    return document + (b" " * (size - len(document)))


def _batch_input(index: int, content: bytes) -> object:
    return _input(
        content,
        path=f"translations/file-{index}.ts",
        layout_identity=f"qt-ts:translations/file-{index}.ts",
    )


def test_qt_hostile_fixture_inventory_fails_atomically_and_source_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, qt = _modules()
    cases = json.loads((_FIXTURES / "invalid_cases.json").read_text())
    attempted_network: list[object] = []

    def fail_external_request(*args: object, **kwargs: object) -> None:
        attempted_network.append((args, kwargs))
        raise AssertionError("XML parsing attempted an external request")

    monkeypatch.setattr("urllib.request.urlopen", fail_external_request)
    for case in cases:
        result = qt.parse_qt_ts(_input(_invalid_case_content(case), path="translations/app_it.ts"))
        assert result.values == (), case["id"]
        assert tuple(issue.code for issue in result.issues) == (case["expected_code"],), case["id"]
        assert len(result.issues) <= 5
        assert all(len(issue.message) <= 256 for issue in result.issues)
        assert all("secret" not in issue.message for issue in result.issues)
        assert all("invalid.example" not in issue.message for issue in result.issues)
        assert all("<" not in issue.message for issue in result.issues)
        assert set(result.issues[0].to_mapping()) == {
            "code",
            "column",
            "line",
            "message",
            "path",
            "repository_side",
        }
    assert attempted_network == []


def test_qt_duplicate_complete_identity_fails_as_duplicate_key() -> None:
    _, qt = _modules()
    duplicate = _document(
        b"<message><source>same</source><translation>one</translation></message>"
        b"<message><source>same</source><translation>two</translation></message>"
    )

    result = qt.parse_qt_ts(_input(duplicate))

    assert result.values == ()
    assert tuple(issue.code for issue in result.issues) == ("duplicate_key",)


def test_qt_empty_document_context_and_translation_are_distinct() -> None:
    _, qt = _modules()
    empty_document = qt.parse_qt_ts(_input(b"<TS version='2.1' language='it-IT'/>"))
    empty_context = qt.parse_qt_ts(
        _input(b"<TS version='2.1' language='it-IT'><context><name>Main</name></context></TS>")
    )
    empty_translation = qt.parse_qt_ts(_input(_document(_message("empty", translation=""))))

    assert empty_document.values == empty_context.values == ()
    assert empty_document.issues == empty_context.issues == ()
    assert len(empty_translation.values) == 1
    assert empty_translation.values[0].display_text == ""


@pytest.mark.parametrize(
    "content",
    (
        _document(_message("unicode", translation="☺")),
        b"\xef\xbb\xbf" + _document(_message("unicode", translation="☺")),
    ),
)
def test_qt_accepts_strict_utf8_with_optional_single_bom(content: bytes) -> None:
    _, qt = _modules()

    result = qt.parse_qt_ts(_input(content))

    assert result.issues == ()
    assert result.values[0].display_text == "☺"


@pytest.mark.parametrize(
    "content",
    (
        _document().decode().encode("utf-16"),
        b"\xff<TS/>",
        b"\xef\xbb\xbf\xef\xbb\xbf<TS version='2.1' language='it'/>",
        b"<TS version='2.1' language='it'>\x00</TS>",
        b"<?xml version='1.0' encoding='iso-8859-1'?><TS version='2.1' language='it'/>",
    ),
)
def test_qt_rejects_unsupported_encoding_and_control_inputs(content: bytes) -> None:
    _, qt = _modules()

    result = qt.parse_qt_ts(_input(content))

    assert result.values == ()
    assert tuple(issue.code for issue in result.issues) == ("malformed_file",)


def test_qt_file_message_location_variant_and_depth_limits_are_exact() -> None:
    _, qt = _modules()
    exact_file = qt.parse_qt_ts(_input(_padded_document(qt.MAX_CANONICAL_FILE_BYTES)))
    over_file = qt.parse_qt_ts(_input(_padded_document(qt.MAX_CANONICAL_FILE_BYTES + 1)))

    exact_messages = qt.parse_qt_ts(
        _input(_document(b"".join(_message(f"key-{index}") for index in range(qt.MAX_QT_MESSAGES))))
    )
    over_messages = qt.parse_qt_ts(
        _input(
            _document(b"".join(_message(f"key-{index}") for index in range(qt.MAX_QT_MESSAGES + 1)))
        )
    )

    exact_locations = qt.parse_qt_ts(
        _input(
            _document(
                b"<message id='located'>"
                + b"<location filename='a.cpp' line='1'/>"
                + (b"<location line='+1'/>" * (qt.MAX_QT_LOCATIONS_PER_MESSAGE - 1))
                + b"<source>x</source><translation>x</translation></message>"
            )
        )
    )
    over_locations = qt.parse_qt_ts(
        _input(
            _document(
                b"<message id='located'>"
                + b"<location filename='a.cpp' line='1'/>"
                + (b"<location line='+1'/>" * qt.MAX_QT_LOCATIONS_PER_MESSAGE)
                + b"<source>x</source><translation>x</translation></message>"
            )
        )
    )

    variants = b"".join(
        f"<lengthvariant priority='{priority}'>x</lengthvariant>".encode()
        for priority in range(1, qt.MAX_QT_VARIANTS_PER_MESSAGE + 1)
    )
    exact_variants = qt.parse_qt_ts(
        _input(
            _document(
                b"<message id='variants'><source>x</source><translation variants='yes'>"
                + variants
                + b"</translation></message>"
            )
        )
    )
    over_variants = qt.parse_qt_ts(
        _input(
            _document(
                b"<message id='variants'><source>x</source><translation variants='yes'>"
                + variants
                + (f"<lengthvariant priority='{qt.MAX_QT_VARIANTS_PER_MESSAGE + 1}'>x").encode()
                + b"</lengthvariant></translation></message>"
            )
        )
    )

    exact_depth = qt.parse_qt_ts(
        _input(
            _document(
                b"<message id='depth' numerus='yes'><source>x</source><translation>"
                b"<numerusform variants='yes'><lengthvariant priority='1'>x</lengthvariant>"
                b"</numerusform></translation></message>"
            )
        )
    )
    over_depth = qt.parse_qt_ts(
        _input(
            _document(
                b"<message id='depth' numerus='yes'><source>x</source><translation>"
                b"<numerusform variants='yes'><lengthvariant priority='1'><b>x</b>"
                b"</lengthvariant></numerusform></translation></message>"
            )
        )
    )

    assert len(exact_file.values) == 1
    assert over_file.values == ()
    assert len(exact_messages.values) == qt.MAX_QT_MESSAGES
    assert over_messages.values == ()
    assert len(_node_fields(exact_locations.values[0], "qt_ts:location")) == (
        qt.MAX_QT_LOCATIONS_PER_MESSAGE
    )
    assert over_locations.values == ()
    assert len(exact_variants.values) == qt.MAX_QT_VARIANTS_PER_MESSAGE
    assert over_variants.values == ()
    assert qt.MAX_QT_XML_DEPTH == 6
    assert len(exact_depth.values) == 1
    assert over_depth.values == ()


def test_qt_peer_files_fail_atomically_and_obey_file_and_aggregate_limits() -> None:
    _, qt = _modules()
    exact_files = tuple(
        cast(Any, _batch_input(index, _document(_message(f"file-{index}"))))
        for index in range(qt.MAX_QT_FILES)
    )
    exact_file_result = qt.parse_qt_ts_files(exact_files)
    over_file_result = qt.parse_qt_ts_files(
        exact_files + (cast(Any, _batch_input(qt.MAX_QT_FILES, _document(_message("over")))),)
    )

    file_count = 21
    per_file, remainder = divmod(qt.MAX_QT_AGGREGATE_BYTES, file_count)
    exact_aggregate = tuple(
        cast(
            Any,
            _batch_input(
                index,
                _padded_document(
                    per_file + (1 if index < remainder else 0), identifier=f"a-{index}"
                ),
            ),
        )
        for index in range(file_count)
    )
    exact_aggregate_result = qt.parse_qt_ts_files(exact_aggregate)
    one_byte_over = replace(
        exact_aggregate[-1],
        content=exact_aggregate[-1].content + b" ",
    )
    over_aggregate_result = qt.parse_qt_ts_files(exact_aggregate[:-1] + (one_byte_over,))

    bad = cast(Any, _batch_input(700, b"<TS"))
    atomic = qt.parse_qt_ts_files((exact_files[0], bad))

    assert len(exact_file_result.values) == qt.MAX_QT_FILES
    assert over_file_result.values == ()
    assert len(exact_aggregate_result.values) == file_count
    assert over_aggregate_result.values == ()
    assert atomic.values == ()
    assert tuple(issue.path for issue in atomic.issues) == ("translations/file-700.ts",)


def test_qt_concurrent_calls_are_byte_equal_and_failure_isolated() -> None:
    _, qt = _modules()
    valid_input = _input()
    invalid_input = _input(
        b"<TS version='2.1' language='it'><context><name>Main</name><message>"
        b"<location line='+1'/><source>x</source><translation>x</translation>"
        b"</message></context></TS>"
    )

    def parse(index: int) -> bytes:
        parser_input = valid_input if index % 2 == 0 else invalid_input
        result = qt.parse_qt_ts(parser_input)
        return json.dumps(result.to_mapping(), sort_keys=True, separators=(",", ":")).encode()

    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = tuple(executor.map(parse, range(64)))

    assert len(set(outputs[::2])) == 1
    assert len(set(outputs[1::2])) == 1
    assert json.loads(outputs[0])["values"]
    assert json.loads(outputs[1])["values"] == []
    after_failure = qt.parse_qt_ts(invalid_input)
    assert after_failure.values == ()
    assert tuple(issue.code for issue in after_failure.issues) == ("ambiguous_structure",)


def test_qt_manifest_covers_required_categories_and_exact_limits() -> None:
    manifest = json.loads((_FIXTURES / "manifest.json").read_text())

    assert set(manifest["categories"]) == {
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
    }
    assert manifest["limits"] == {
        "file_bytes": 1_048_576,
        "aggregate_bytes": 20_971_520,
        "files": 500,
        "messages": 5_000,
        "values": 5_000,
        "depth": 6,
        "locations_per_message": 256,
        "variants_per_message": 256,
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
def test_arbitrary_qt_bytes_never_escape_or_return_partial_values(payload: bytes) -> None:
    _, qt = _modules()

    result = qt.parse_qt_ts(_input(payload))

    assert not (result.values and result.issues)
    assert len(result.issues) <= 5
    assert all(len(issue.message) <= 256 for issue in result.issues)
