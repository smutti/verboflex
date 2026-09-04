"""Golden contracts for the strict canonical iOS ``.strings`` adapter."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

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
            _fields(node)["raw"]
            for node in value.structure
            if node.kind == "ios_strings:comment"
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
    assert all(value.selector == core.CanonicalSelector(kind="scalar", fields=()) for value in result.values)


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
    comments = [
        _fields(node)
        for node in value.structure
        if node.kind == "ios_strings:comment"
    ]
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
        if node.kind in {"ios_strings:comment", "ios_strings:whitespace", "ios_strings:key", "ios_strings:value"}:
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
    assert all(left[1] == right[0] for left, right in zip(pieces, pieces[1:], strict=True))


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
    assert result.issues[0].code in {"malformed_file", "ambiguous_structure", "unsupported_structure"}
    assert "plural" not in result.issues[0].message
