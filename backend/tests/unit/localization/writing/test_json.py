"""Exact JSON value-token editing under strict canonical layout authority."""

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
    SourceFileSnapshot,
    WritebackReason,
    WritebackRejected,
    WriteEdit,
)

from ._support import edit, render, snapshot

FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization"


def _source(content: bytes, *, rooted: bool = False, **changes: object) -> SourceFileSnapshot:
    fields: dict[str, object] = {
        "format": "json",
        "path": "locales.json" if rooted else "assets/it_IT/messages.json",
        "layout_identity": (
            "json:locale-rooted:locales.json"
            if rooted
            else "json:flat-per-locale:assets/{locale}/messages.json"
        ),
        "repository_side": "translations",
    }
    fields.update(changes)
    return snapshot(content, **fields)


def _localized_edit(source: SourceFileSnapshot, key: str, text: str) -> WriteEdit:
    values = parse_canonical_snapshot(source.parser_input).values
    value = next(v for v in values if v.logical_key == key and v.language == "it-IT")
    return WriteEdit(key, value.language, value.selector, value.locator, value.display_text, text)


def test_multiedit_preserves_every_unselected_token() -> None:
    source = _source((FIXTURES / "writing/json/nested.json").read_bytes(), rooted=True)
    edits = (
        _localized_edit(source, "title", 'Pay "now" 😀'),
        _localized_edit(source, "literal.dot[0]/~", "Line\r\nnext"),
        _localized_edit(source, "escaped.key", "é"),
    )
    expected = (FIXTURES / "writing/json/nested.expected.json").read_bytes()
    assert render(source, *edits).content == expected
    assert render(source, *reversed(edits)).content == expected
    assert set(render(source, *edits).changed_edits) == set(edits)


def test_parent_segments_and_literal_punctuation_do_not_collide() -> None:
    content = b'{"a.b":{"x":"one"},"a":{"b":{"x":"two"}},"a/b[0]~":"three"}'
    source = _source(content)
    changes = (
        edit(source, "x", "first", parents=("a.b",)),
        edit(source, "x", "second", parents=("a", "b")),
        edit(source, "a/b[0]~", "third", parents=()),
    )
    assert render(source, *changes).content == (
        b'{"a.b":{"x":"first"},"a":{"b":{"x":"second"}},"a/b[0]~":"third"}'
    )


def test_escaped_key_identity_is_exact() -> None:
    content = b'{"parent\\u002fkey":{"quote\\"\\\\key":"old"},"plain":"keep"}'
    source = _source(content)
    result = render(source, edit(source, 'quote"\\key', "new", parents=("parent/key",)))
    assert result.content == content.replace(b'"old"', b'"new"')


def test_locale_root_spelling_is_retained() -> None:
    content = b'{"it_\\u0049T":{"k":"old"},"en":{"k":"keep"}}'
    source = _source(content, rooted=True)
    assert render(source, _localized_edit(source, "k", "new")).content == content.replace(
        b'"old"', b'"new"'
    )


def test_crlf_order_trailing_space_and_noop_are_exact() -> None:
    content = b' {\r\n "z" : "old",\r\n "a": "\\u0061"\r\n}  \r\n'
    source = _source(content)
    assert render(source, edit(source, "a", "a")).content is content
    assert render(source, edit(source, "z", "new")).content == content.replace(b"old", b"new")


def test_duplicate_file_refuses_unique_selected_sibling() -> None:
    source = _source(b'{"safe":"old","k":"a","k":"b"}')
    good = _source(b'{"safe":"old","k":"a"}')
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(good, "safe", "new"))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


@pytest.mark.parametrize("case", json.loads((FIXTURES / "json/invalid_cases.json").read_text()))
def test_existing_strict_rejections_remain_explicit(case: dict[str, str]) -> None:
    content = (
        bytes.fromhex(case["content_hex"]) if "content_hex" in case else case["content"].encode()
    )
    with pytest.raises(WritebackRejected) as error:
        render(_source(content, rooted=case["layout"] == "rooted"))
    assert error.value.reason == WritebackReason.UNSUPPORTED_SHAPE


@pytest.mark.parametrize("replacement", ["\x00", "\x01", "\x7f", "\ud800"])
def test_invalid_replacement_is_atomic_and_private(replacement: str) -> None:
    source = _source(b'{"a":"old","b":"keep"}')
    with pytest.raises(WritebackRejected) as error:
        render(source, edit(source, "b", "valid"), edit(source, "a", replacement))
    assert error.value.reason == WritebackReason.INVALID_REPLACEMENT
    assert "old" not in str(error.value)


def test_stale_typed_address_is_rejected() -> None:
    source = _source(b'{"k":"old"}')
    change = edit(source, "k", "new")
    stale = replace(
        change, locator=replace(change.locator, structural_address=("document", "k", 1))
    )
    with pytest.raises(WritebackRejected) as error:
        render(source, stale)
    assert error.value.reason == WritebackReason.AMBIGUOUS_LOCATOR


def test_encoded_replacement_budget_stops_early() -> None:
    source = _source(json.dumps({f"k{i}": "x" for i in range(64)}).encode())
    changes = tuple(edit(source, f"k{i}", "x" * 32768) for i in range(64))
    adapter = importlib.import_module("verboflex.localization.writing.json")
    with (
        patch.object(adapter, "encode_text", wraps=adapter.encode_text) as encoder,
        pytest.raises(WritebackRejected) as error,
    ):
        render(source, *changes)
    assert error.value.reason == WritebackReason.LIMIT_EXCEEDED
    assert encoder.call_count <= 33


@settings(max_examples=70)
@given(st.text(st.characters(blacklist_categories=("Cs", "Cc")), max_size=80))
def test_unicode_replacement_preserves_unselected_raw_tokens(text: str) -> None:
    content = b'{"k":"old","keep":"\\u0061", "nested": {"k": "unchanged"}}'
    source = _source(content)
    result = render(source, edit(source, "k", text, parents=()))
    expected = content.replace(b'"old"', json.dumps(text, ensure_ascii=False).encode())
    assert result.content == expected
    reparsed = parse_canonical_snapshot(replace(source.parser_input, content=result.content))
    assert not reparsed.issues
    assert (
        next(
            v
            for v in reparsed.values
            if dict(v.selector.fields)["parents"] == () and v.logical_key == "k"
        ).display_text
        == text
    )
