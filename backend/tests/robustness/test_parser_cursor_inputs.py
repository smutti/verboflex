"""Generated corrupt files and cursor mutations at trust boundaries."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.localization.importing.test_conformance import _canonical_bytes, _input
from verboflex.localization.importing import core, registry
from verboflex.services.signed_cursor import (
    CursorBinding,
    CursorPosition,
    InvalidSignedCursor,
    SignedCursorCodec,
)

FORMATS = ("android_xml", "qt_ts", "json", "ios_strings", "xliff")
FUZZ = settings(max_examples=300, deadline=None)


def assert_safe_result(parser_input):
    result = registry.parse_canonical_snapshot(parser_input)
    assert core.canonical_result_is_valid(result)
    assert len(result.issues) <= 5
    assert all(len(issue.message) <= 256 for issue in result.issues)
    encoded = _canonical_bytes(result)
    assert b"Traceback" not in encoded
    assert encoded == _canonical_bytes(registry.parse_canonical_snapshot(parser_input))
    if result.issues:
        assert not result.values


@pytest.mark.parametrize("format_name", FORMATS)
@FUZZ
@given(raw=st.binary(max_size=4096))
def test_random_bytes_have_bounded_deterministic_parser_result(format_name, raw):
    assert_safe_result(_input(format_name, content=raw))


@pytest.mark.parametrize("format_name", FORMATS)
@FUZZ
@given(
    position=st.integers(min_value=0, max_value=10000),
    fragment=st.binary(max_size=64),
    delete=st.integers(min_value=0, max_value=100),
)
def test_mutating_valid_files_exercises_deeper_parser_paths(
    format_name, position, fragment, delete
):
    original = _input(format_name).content
    offset = position % (len(original) + 1)
    modified = original[:offset] + fragment + original[offset + delete :]
    assert_safe_result(_input(format_name, content=modified))


@pytest.mark.parametrize("text", ["\x00", "\ud800", "\udfff", "x\ud800y"])
@pytest.mark.parametrize("field", ["key", "value"])
def test_json_escaped_invalid_unicode_never_reaches_canonical_storage(text, field):
    content = json.dumps(
        {"en": {text if field == "key" else "key": text if field == "value" else "value"}}
    ).encode()
    result = registry.parse_canonical_snapshot(_input("json", content=content))
    assert result.issues and not result.values
    _canonical_bytes(result)


def binding():
    return CursorBinding(
        kind="search", principal_id=UUID(int=1), scope="all", filters={"q": "日本語"}, page_size=50
    )


@FUZZ
@given(raw=st.text(max_size=4096))
def test_arbitrary_cursors_fail_closed(raw):
    with pytest.raises(InvalidSignedCursor, match="^invalid cursor$"):
        SignedCursorCodec("test-secret").decode(raw, binding=binding())


@FUZZ
@given(
    position=st.integers(min_value=0, max_value=10000),
    replacement=st.sampled_from(tuple("ABCxyz019_-")),
)
def test_tampered_cursor_or_different_user_cannot_resume_a_page(position, replacement):
    codec = SignedCursorCodec("test-secret")
    expected = CursorPosition(created_at=datetime(2026, 1, 1, tzinfo=UTC), id=UUID(int=2))
    token = codec.encode(binding=binding(), position=expected)
    assert codec.decode(token, binding=binding()) == expected
    index = position % len(token)
    character = replacement if token[index] != replacement else "!"
    mutated = token[:index] + character + token[index + 1 :]
    with pytest.raises(InvalidSignedCursor):
        codec.decode(mutated, binding=binding())
    with pytest.raises(InvalidSignedCursor):
        codec.decode(token, binding=replace(binding(), principal_id=UUID(int=3)))
