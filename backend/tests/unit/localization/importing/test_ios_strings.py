"""Golden contracts for the strict canonical iOS ``.strings`` adapter."""

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

_FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization" / "ios"


def _modules() -> tuple[Any, Any]:
    core = importlib.import_module("verboflex.localization.importing.core")
    try:
        adapter = importlib.import_module("verboflex.localization.importing.ios_strings")
    except ModuleNotFoundError:
        pytest.fail("canonical iOS strings adapter is not implemented")
    return core, adapter


def _input(content: bytes | None = None, **overrides: object) -> object:
    core = importlib.import_module("verboflex.localization.importing.core")
    fields: dict[str, object] = {
        "format": "ios_strings",
        "repository_side": "translations",
        "path": "mobile/it_IT.lproj/Localizable.strings",
        "content": content if content is not None else (_FIXTURES / "valid.strings").read_bytes(),
        "layout_identity": "ios-strings:mobile/{locale}.lproj/Localizable.strings",
        "layout_version": 1,
        "base_language": "en",
    }
    fields.update(overrides)
    return core.CanonicalParserInput(**fields)


def _fields(node: object) -> dict[str, object]:
    return dict(node.fields)  # type: ignore[attr-defined]


def _node(value: object, kind: str) -> object:
    return next(node for node in value.structure if node.kind == kind)  # type: ignore[attr-defined]


def _projection(result: object) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for value in sorted(result.values, key=lambda item: item.locator.position):  # type: ignore[attr-defined]
        encoding = _fields(_node(value, "ios_strings:encoding"))
        key = _fields(_node(value, "ios_strings:key"))
        translated_value = _fields(_node(value, "ios_strings:value"))
        comments = [
            _fields(node)["raw"] for node in value.structure if node.kind == "ios_strings:comment"
        ]
        entries.append(
            {
                "bom": encoding["bom"],
                "comments": comments,
                "display_text": value.display_text,
                "encoding": encoding["encoding"],
                "language": value.language,
                "logical_key": value.logical_key,
                "position": value.locator.position,
                "raw_key": key["raw"],
                "raw_value": translated_value["raw"],
                "source_text": value.source_text,
                "translated_text": value.translated_text,
            }
        )
    return {"entries": entries, "format": "ios_strings"}


def test_ios_valid_golden_manifest_emits_complete_scalar_values() -> None:
    core, adapter = _modules()
    expected = json.loads((_FIXTURES / "valid.expected.json").read_text())

    result = adapter.parse_ios_strings(_input())

    assert result.issues == ()
    assert _projection(result) == expected
    assert result.values == tuple(sorted(result.values, key=core.canonical_value_order))
    assert all(
        value.selector == core.CanonicalSelector(kind="scalar", fields=())
        for value in result.values
    )


@pytest.mark.parametrize(
    ("content", "encoding", "bom"),
    (
        (b'"greeting" = "Hello";', "utf-8", "none"),
        (b"\xef\xbb\xbf" + b'"greeting" = "Hello";', "utf-8", "utf-8"),
        (
            b"\xff\xfe" + '"greeting" = "Hello";'.encode("utf-16-le"),
            "utf-16-le",
            "utf-16-le",
        ),
        (
            b"\xfe\xff" + '"greeting" = "Hello";'.encode("utf-16-be"),
            "utf-16-be",
            "utf-16-be",
        ),
    ),
)
def test_ios_encoding_variants_have_equal_semantics_and_distinct_metadata(
    content: bytes,
    encoding: str,
    bom: str,
) -> None:
    _, adapter = _modules()

    result = adapter.parse_ios_strings(_input(content))

    assert result.issues == ()
    assert len(result.values) == 1
    value = result.values[0]
    assert (value.logical_key, value.display_text) == ("greeting", "Hello")
    assert _fields(_node(value, "ios_strings:encoding")) == {
        "encoding": encoding,
        "bom": bom,
    }


def test_ios_escape_sequences_decode_without_losing_lexical_style() -> None:
    _, adapter = _modules()
    content = (
        b'"key\\U002Ename" = '
        b'"quote:\\" slash:\\\\ newline:\\n tab:\\t return:\\r emoji:\\UD83D\\UDE00";'
    )

    result = adapter.parse_ios_strings(_input(content))

    assert result.issues == ()
    value = result.values[0]
    assert value.logical_key == "key.name"
    assert value.display_text == 'quote:" slash:\\ newline:\n tab:\t return:\r emoji:😀'
    key = _fields(_node(value, "ios_strings:key"))
    translated_value = _fields(_node(value, "ios_strings:value"))
    assert key["quote_style"] == translated_value["quote_style"] == "double"
    assert key["escape_style"] == translated_value["escape_style"] == "backslash"
    assert key["escapes"] == ("\\U002E",)
    assert translated_value["escapes"] == (
        '\\"',
        "\\\\",
        "\\n",
        "\\t",
        "\\r",
        "\\UD83D",
        "\\UDE00",
    )


def test_ios_comments_whitespace_and_source_spans_preserve_the_document() -> None:
    _, adapter = _modules()
    source = '/* before */\n"hello" /* key gap */ = // value gap\n "Hi"; // after\n'

    result = adapter.parse_ios_strings(_input(source.encode()))

    assert result.issues == ()
    value = result.values[0]
    comments = [_fields(node) for node in value.structure if node.kind == "ios_strings:comment"]
    assert [(item["style"], item["raw"], item["placement"]) for item in comments] == [
        ("block", "/* before */", "before_entry"),
        ("block", "/* key gap */", "after_key"),
        ("line", "// value gap", "after_equals"),
        ("line", "// after", "after_document"),
    ]
    assert value.locator.line == 2
    assert value.locator.column == 1

    pieces: list[tuple[int, int, str]] = []
    for node in value.structure:
        fields = _fields(node)
        if node.kind in {
            "ios_strings:comment",
            "ios_strings:whitespace",
            "ios_strings:key",
            "ios_strings:value",
        }:
            pieces.append((int(fields["span_start"]), int(fields["span_end"]), str(fields["raw"])))
    entry = _fields(_node(value, "ios_strings:entry"))
    pieces.extend(
        (
            (int(entry["equals_start"]), int(entry["equals_end"]), "="),
            (int(entry["semicolon_start"]), int(entry["semicolon_end"]), ";"),
        )
    )
    pieces.sort()
    assert "".join(raw for _, _, raw in pieces) == source
    assert all(source[start:end] == raw for start, end, raw in pieces)
    assert all(left[1] == right[0] for left, right in zip(pieces, pieces[1:], strict=False))


def test_ios_valid_empty_value_remains_explicit_and_side_projection_is_exact() -> None:
    _, adapter = _modules()
    content = b'"empty" = "";'

    translation = adapter.parse_ios_strings(_input(content))
    source = adapter.parse_ios_strings(
        _input(
            content,
            repository_side="direct",
            path="mobile/en.lproj/Localizable.strings",
            layout_identity="ios-strings:mobile/{locale}.lproj/Localizable.strings",
        )
    )

    assert translation.issues == source.issues == ()
    assert translation.values[0].display_text == translation.values[0].translated_text == ""
    assert translation.values[0].source_text is None
    assert source.values[0].display_text == source.values[0].source_text == ""
    assert source.values[0].translated_text is None


@pytest.mark.parametrize(
    ("content", "overrides"),
    (
        (b'"plural" = {"one" = "One";};', {}),
        (b'hello = "Hello";', {}),
        (b'#define HELLO "Hello"', {}),
        (b'"hello" = "Hello"; trailing', {}),
        (
            b'"hello" = "Hello";',
            {
                "path": "mobile/it.lproj/Localizable.stringsdict",
                "layout_identity": "ios-strings:mobile/{locale}.lproj/Localizable.stringsdict",
            },
        ),
    ),
)
def test_ios_comment_and_assignment_grammar_rejects_non_strings_constructs(
    content: bytes,
    overrides: dict[str, object],
) -> None:
    _, adapter = _modules()

    result = adapter.parse_ios_strings(_input(content, **overrides))

    assert result.values == ()
    assert len(result.issues) == 1
    assert result.issues[0].code in {
        "malformed_file",
        "ambiguous_structure",
        "unsupported_structure",
    }
    assert "plural" not in result.issues[0].message


def _invalid_case_content(case: dict[str, object]) -> bytes:
    content = case.get("content")
    if isinstance(content, str):
        return content.encode()
    content_hex = case.get("content_hex")
    assert isinstance(content_hex, str)
    return bytes.fromhex(content_hex)


def _assignments(count: int, *, start: int = 0) -> bytes:
    return b"".join(f'"key-{index}"="value";'.encode() for index in range(start, start + count))


def _peer_input(content: bytes, *, index: int) -> object:
    return _input(
        content,
        path=f"catalogs/en.lproj/file-{index}.strings",
        layout_identity=f"ios-strings:catalogs/{{locale}}.lproj/file-{index}.strings",
        repository_side="direct",
    )


def _padded_assignment(size: int, *, index: int) -> bytes:
    document = f'"key-{index}"="value";'.encode()
    assert len(document) <= size
    return document + (b" " * (size - len(document)))


def test_ios_hostile_fixture_inventory_fails_atomically_and_source_free() -> None:
    _, adapter = _modules()
    cases = json.loads((_FIXTURES / "invalid_cases.json").read_text())

    for case in cases:
        content = _invalid_case_content(case)
        result = adapter.parse_ios_strings(_input(content))

        assert result.values == (), case["id"]
        assert tuple(issue.code for issue in result.issues) == (case["expected_code"],), case["id"]
        assert len(result.issues) <= adapter.MAX_IOS_ISSUES
        assert all(len(issue.message) <= 256 for issue in result.issues)
        assert all("secret" not in issue.message.lower() for issue in result.issues)
        assert all("<" not in issue.message for issue in result.issues)
        assert set(result.issues[0].to_mapping()) == {
            "code",
            "column",
            "line",
            "message",
            "path",
            "repository_side",
        }


def test_ios_file_assignment_comment_token_and_escape_limits_are_exact() -> None:
    _, adapter = _modules()

    exact_file = adapter.parse_ios_strings(
        _input(_padded_assignment(adapter.MAX_CANONICAL_FILE_BYTES, index=0))
    )
    over_file = adapter.parse_ios_strings(
        _input(_padded_assignment(adapter.MAX_CANONICAL_FILE_BYTES + 1, index=0))
    )
    exact_assignments = adapter.parse_ios_strings(_input(_assignments(adapter.MAX_IOS_ASSIGNMENTS)))
    over_assignments = adapter.parse_ios_strings(
        _input(_assignments(adapter.MAX_IOS_ASSIGNMENTS + 1))
    )
    exact_comments = adapter.parse_ios_strings(
        _input((b"/**/" * adapter.MAX_IOS_COMMENTS) + b'"key"="value";')
    )
    over_comments = adapter.parse_ios_strings(
        _input((b"/**/" * (adapter.MAX_IOS_COMMENTS + 1)) + b'"key"="value";')
    )
    token_assignments = (adapter.MAX_IOS_TOKENS - 4_000) // 4
    exact_tokens_content = (b"/**/" * 4_000) + _assignments(token_assignments)
    exact_tokens = adapter.parse_ios_strings(_input(exact_tokens_content))
    over_tokens = adapter.parse_ios_strings(_input(b" " + exact_tokens_content))
    exact_escapes = adapter.parse_ios_strings(
        _input(b'"key"="' + (b"\\n" * adapter.MAX_IOS_ESCAPES_PER_TOKEN) + b'";')
    )
    over_escapes = adapter.parse_ios_strings(
        _input(b'"key"="' + (b"\\n" * (adapter.MAX_IOS_ESCAPES_PER_TOKEN + 1)) + b'";')
    )

    assert len(exact_file.values) == 1
    assert over_file.values == () and over_file.issues
    assert len(exact_assignments.values) == adapter.MAX_IOS_ASSIGNMENTS
    assert over_assignments.values == () and over_assignments.issues
    assert len(exact_comments.values) == 1
    assert over_comments.values == () and over_comments.issues
    assert len(exact_tokens.values) == token_assignments
    assert over_tokens.values == () and over_tokens.issues
    assert len(exact_escapes.values) == 1
    assert over_escapes.values == () and over_escapes.issues


def test_ios_peer_files_fail_atomically_and_obey_file_and_aggregate_limits() -> None:
    _, adapter = _modules()
    exact_files = tuple(
        cast(Any, _peer_input(f'"key-{index}"="value";'.encode(), index=index))
        for index in range(adapter.MAX_IOS_FILES)
    )
    exact_file_result = adapter.parse_ios_strings_files(exact_files)
    over_file_result = adapter.parse_ios_strings_files(
        exact_files
        + (
            cast(
                Any,
                _peer_input(
                    f'"key-{adapter.MAX_IOS_FILES}"="value";'.encode(),
                    index=adapter.MAX_IOS_FILES,
                ),
            ),
        )
    )

    file_count = 21
    per_file, remainder = divmod(adapter.MAX_IOS_AGGREGATE_BYTES, file_count)
    exact_aggregate = tuple(
        cast(
            Any,
            _peer_input(
                _padded_assignment(per_file + (1 if index < remainder else 0), index=index),
                index=index,
            ),
        )
        for index in range(file_count)
    )
    exact_aggregate_result = adapter.parse_ios_strings_files(exact_aggregate)
    one_byte_over = replace(
        exact_aggregate[-1],
        content=exact_aggregate[-1].content + b" ",
    )
    over_aggregate_result = adapter.parse_ios_strings_files(exact_aggregate[:-1] + (one_byte_over,))
    malformed = cast(Any, _peer_input(b'"bad"="unterminated', index=700))
    atomic = adapter.parse_ios_strings_files((exact_files[0], malformed))

    assert len(exact_file_result.values) == adapter.MAX_IOS_FILES
    assert over_file_result.values == () and over_file_result.issues
    assert len(exact_aggregate_result.values) == file_count
    assert over_aggregate_result.values == () and over_aggregate_result.issues
    assert atomic.values == ()
    assert tuple(issue.path for issue in atomic.issues) == ("catalogs/en.lproj/file-700.strings",)


def test_ios_concurrent_calls_are_byte_equal_and_failure_isolated() -> None:
    _, adapter = _modules()
    valid_input = _input()
    invalid_input = _input(b'"safe"="discarded";"bad"="unterminated')

    def parse(index: int) -> bytes:
        parser_input = valid_input if index % 2 == 0 else invalid_input
        result = adapter.parse_ios_strings(parser_input)
        return json.dumps(result.to_mapping(), sort_keys=True, separators=(",", ":")).encode()

    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = tuple(executor.map(parse, range(64)))

    assert len(set(outputs[::2])) == 1
    assert len(set(outputs[1::2])) == 1
    assert json.loads(outputs[0])["values"]
    assert json.loads(outputs[1])["values"] == []
    after_failure = adapter.parse_ios_strings(invalid_input)
    assert after_failure.values == ()
    assert tuple(issue.code for issue in after_failure.issues) == ("malformed_file",)


def test_ios_input_authority_and_safe_coordinates_are_closed() -> None:
    _, adapter = _modules()

    missing_base = adapter.parse_ios_strings(_input(base_language=""))
    wrong_layout = adapter.parse_ios_strings(_input(layout_identity="ios-strings:wrong"))
    malformed = adapter.parse_ios_strings(_input(b'// line\n"safe"="discarded"'))

    assert tuple(issue.code for issue in missing_base.issues) == ("base_language_required",)
    assert tuple(issue.code for issue in wrong_layout.issues) == ("ambiguous_structure",)
    assert malformed.values == ()
    assert [(issue.line, issue.column) for issue in malformed.issues] == [(2, 19)]
    assert all(
        coordinate is None or 1 <= coordinate <= 2_147_483_647
        for issue in malformed.issues
        for coordinate in (issue.line, issue.column)
    )


def test_ios_manifest_covers_required_categories_and_exact_limits() -> None:
    manifest = json.loads((_FIXTURES / "manifest.json").read_text())

    assert set(manifest["categories"]) == {
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
    }
    assert manifest["limits"] == {
        "file_bytes": 1_048_576,
        "aggregate_bytes": 20_971_520,
        "files": 500,
        "assignments": 5_000,
        "comments": 4_096,
        "tokens": 20_000,
        "escapes_per_token": 4_096,
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
def test_arbitrary_ios_bytes_never_escape_or_return_partial_values(payload: bytes) -> None:
    _, adapter = _modules()

    result = adapter.parse_ios_strings(_input(payload))

    assert not (result.values and result.issues)
    assert len(result.issues) <= 5
    assert all(len(issue.message) <= 256 for issue in result.issues)
    assert all(
        issue.message
        in {
            "Malformed iOS strings file.",
            "Ambiguous iOS strings layout.",
            "Unsupported iOS strings structure.",
            "Duplicate iOS strings key.",
            "Base language is required.",
        }
        for issue in result.issues
    )
