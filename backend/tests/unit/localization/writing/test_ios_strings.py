"""iOS original-codec and token-complement preservation contracts."""

from __future__ import annotations

import importlib
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.writing.core import (
    ByteEdit,
    SourceFileSnapshot,
    WritebackReason,
    WritebackRejected,
)

from ._support import edit, render, snapshot

FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization"
CODECS = [
    ("utf-8", b""),
    ("utf-8", b"\xef\xbb\xbf"),
    ("utf-16-le", b"\xff\xfe"),
    ("utf-16-be", b"\xfe\xff"),
]


def _source(content: bytes, **changes: object) -> SourceFileSnapshot:
    fields: dict[str, object] = {
        "format": "ios_strings",
        "path": "mobile/it_IT.lproj/Localizable.strings",
        "layout_identity": "ios-strings:mobile/{locale}.lproj/Localizable.strings",
        "repository_side": "translations",
    }
    fields.update(changes)
    return snapshot(content, **fields)


@pytest.mark.parametrize(("codec", "bom"), CODECS)
def test_utf16_le_and_be_preserve_bom_and_crlf(codec: str, bom: bytes) -> None:
    original = (FIXTURES / "writing/ios/catalog.strings").read_text().replace("\n", "\r\n")
    expected = (FIXTURES / "writing/ios/catalog.expected.strings").read_text().replace("\n", "\r\n")
    source = _source(bom + original.encode(codec))
    changes = (
        edit(source, "welcome.title", 'Say "ciao" \\ path\nnext\rend\t😀'),
        edit(source, "empty", "Filled é"),
    )
    result = render(source, *changes)
    assert result.content == bom + expected.encode(codec)
    assert render(source, *reversed(changes)).content == result.content
    assert result.original_bytes == source.parser_input.content
    assert set(result.changed_edits) == set(changes)


@pytest.mark.parametrize(("codec", "bom"), CODECS)
def test_supplementary_character_before_target_uses_encoded_prefix(codec: str, bom: bytes) -> None:
    original = '/* 😀 é */ "😀"="😀"; "target"="old"; "end"="keep";'
    content = bom + original.encode(codec)
    source = _source(content)
    result = render(source, edit(source, "target", "😀 longer é"))
    assert result.content == content.replace('"old"'.encode(codec), '"😀 longer é"'.encode(codec))


def test_length_change_does_not_fail_unchanged_sibling_semantics() -> None:
    original = b'"first"="old";\r\n/* keep */ "second" = "escaped\\U00E9"; // tail\r\n'
    source = _source(original)
    assert render(source, edit(source, "first", "Much longer text\nsecond line")).content == (
        original.replace(b'"old"', b'"Much longer text\\nsecond line"')
    )


@pytest.mark.parametrize(("codec", "bom"), CODECS)
def test_noop_preserves_original_escape_spelling(codec: str, bom: bytes) -> None:
    content = bom + '"key\\U002Ename"="\\UD83D\\UDE00";'.encode(codec)
    source = _source(content)
    result = render(source, edit(source, "key.name", "😀"))
    assert result.content is content
    assert result.changed_edits == ()


@pytest.mark.parametrize("text", ['"\\\n\r\t', "😀é\ufeff", "", '/* text */ ; = "key"'])
def test_quotes_unicode_and_control_escapes_round_trip(text: str) -> None:
    source = _source(b'"key"="old"; "keep"="unchanged";')
    result = render(source, edit(source, "key", text))
    parsed = parse_canonical_snapshot(replace(source.parser_input, content=result.content))
    assert not parsed.issues
    assert next(v for v in parsed.values if v.logical_key == "key").display_text == text
    assert result.content.endswith(b'; "keep"="unchanged";')


@pytest.mark.parametrize("case", json.loads((FIXTURES / "ios/invalid_cases.json").read_text()))
def test_strict_invalid_documents_have_typed_failure(case: dict[str, str]) -> None:
    content = (
        bytes.fromhex(case["content_hex"]) if "content_hex" in case else case["content"].encode()
    )
    with pytest.raises(WritebackRejected) as error:
        render(_source(content))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


def test_duplicate_file_refuses_unique_selected_sibling() -> None:
    source = _source(b'"safe"="old";"k"="a";"k"="b";')
    good = _source(b'"safe"="old";"k"="a";')
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(good, "safe", "new"))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


@pytest.mark.parametrize("text", ["\x00", "\x01", "\x7f", "\ud800"])
def test_invalid_replacement_is_atomic(text: str) -> None:
    source = _source(b'"a"="old"; "b"="keep";')
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "b", "valid"), edit(source, "a", text))
    assert error.value.reason == WritebackReason.INVALID_REPLACEMENT


@pytest.mark.parametrize("text", ["\\" * 4097, "\n" * 4097], ids=["slashes", "newlines"])
def test_existing_escape_count_ceiling_is_enforced_before_output(text: str) -> None:
    source = _source(b'"key"="old";')
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "key", text))
    assert error.value.reason == WritebackReason.LIMIT_EXCEEDED


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (b'"stable"', b'"st\\U0061ble"'),
        (b"/* comment */", b"/* changed */"),
        (b'"raw\\U00E9"', '"rawé"'.encode()),
    ],
)
def test_semantic_proof_still_checks_unselected_raw_key_value_and_comment(
    before: bytes,
    after: bytes,
) -> None:
    content = b'"target"="old"; /* comment */ "stable"="raw\\U00E9";'
    source = _source(content)
    adapter = importlib.import_module("verboflex.localization.writing.ios_strings")
    planner = adapter.plan_edits

    def corrupt(*args: object) -> tuple[ByteEdit, ...]:
        changes = planner(*args)
        start = content.index(before)
        return (*changes, ByteEdit(start, start + len(before), after))

    with (
        patch.object(adapter, "plan_edits", side_effect=corrupt),
        pytest.raises(WritebackRejected) as error,
    ):
        render(source, edit(source, "target", "new"))
    assert error.value.reason == WritebackReason.INVALID_OUTPUT


def test_encoded_replacement_budget_stops_early() -> None:
    source = _source("".join(f'"k{i}"="x";' for i in range(64)).encode())
    changes = tuple(edit(source, f"k{i}", "x" * 32768) for i in range(64))
    adapter = importlib.import_module("verboflex.localization.writing.ios_strings")
    with (
        patch.object(adapter, "encode_text", wraps=adapter.encode_text) as encoder,
        pytest.raises(WritebackRejected) as error,
    ):
        render(source, *changes)
    assert error.value.reason == WritebackReason.LIMIT_EXCEEDED
    assert encoder.call_count <= 33


@settings(max_examples=70)
@given(
    st.text(st.characters(blacklist_categories=("Cs", "Cc")), max_size=80),
    st.sampled_from(CODECS),
)
def test_unicode_and_codec_property_preserves_unselected_tokens(
    text: str,
    encoding: tuple[str, bytes],
) -> None:
    codec, bom = encoding
    original = '/* 😀 */ "k"="old"; "stable"="\\U00E9"; // end\r\n'
    source = _source(bom + original.encode(codec))
    result = render(source, edit(source, "k", text))
    parsed = parse_canonical_snapshot(replace(source.parser_input, content=result.content))
    assert not parsed.issues
    assert next(v for v in parsed.values if v.logical_key == "k").display_text == text
    assert result.content.startswith(bom + '/* 😀 */ "k"='.encode(codec))
    assert result.content.endswith('; "stable"="\\U00E9"; // end\r\n'.encode(codec))
