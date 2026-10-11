"""Byte-exact safety proof for simultaneous edits against immutable offsets."""

from __future__ import annotations

import importlib
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st


def _core() -> Any:
    try:
        return importlib.import_module("verboflex.localization.writing.core")
    except ModuleNotFoundError:
        pytest.fail("The deterministic byte-edit preservation kernel is not implemented")


def test_unchanged_byte_complement() -> None:
    core = _core()
    content = b"AA__BB__CC"
    edits = (core.ByteEdit(2, 4, b"one"), core.ByteEdit(6, 8, b"XYZlong"))
    assert core.apply_byte_edits(content, edits) == b"AAoneBBXYZlongCC"
    assert core.apply_byte_edits(content, tuple(reversed(edits))) == b"AAoneBBXYZlongCC"
    assert content == b"AA__BB__CC"


def test_noop_retains_original_bytes() -> None:
    core = _core()
    content = b"\xef\xbb\xbf<original />\r\n"
    assert core.apply_byte_edits(content, ()) is content
    assert core.apply_byte_edits(content, (core.ByteEdit(3, 15, content[3:15]),)) == content


def test_parallel_rendering_is_deterministic_and_pure() -> None:
    core = _core()
    content = b"before|one|middle|two|after"
    edits = (core.ByteEdit(7, 10, b"1"), core.ByteEdit(18, 21, b"SECOND"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(lambda _: core.apply_byte_edits(content, edits), range(24)))
    assert outputs == [b"before|1|middle|SECOND|after"] * 24
    assert content == b"before|one|middle|two|after"


def test_interrupted_render_emits_no_partial_output() -> None:
    core = _core()
    original = b"AAxxBBzzCC"
    edits = (core.ByteEdit(2, 4, b"changed"), core.ByteEdit(3, 6, b"overlap"))
    with pytest.raises(core.WritebackRejected):
        core.apply_byte_edits(original, edits)
    assert original == b"AAxxBBzzCC"
    assert core.apply_byte_edits(original, (edits[0],)) == b"AAchangedBBzzCC"


@pytest.mark.parametrize(
    "spans", [((0, 3), (2, 4)), ((1, 1), (1, 1)), ((0, 2), (0, 2)), ((0, 4), (1, 2))]
)
def test_overlapping_spans_are_rejected(spans: tuple[tuple[int, int], ...]) -> None:
    core = _core()
    with pytest.raises(core.WritebackRejected) as error:
        core.apply_byte_edits(b"original", tuple(core.ByteEdit(a, b, b"X") for a, b in spans))
    assert error.value.reason == core.WritebackReason.AMBIGUOUS_LOCATOR


def test_adjacent_spans_and_boundary_insertions_are_local() -> None:
    core = _core()
    assert (
        core.apply_byte_edits(b"ab", (core.ByteEdit(0, 1, b"A"), core.ByteEdit(1, 2, b"B")))
        == b"AB"
    )
    assert (
        core.apply_byte_edits(b"ab", (core.ByteEdit(0, 0, b"["), core.ByteEdit(2, 2, b"]")))
        == b"[ab]"
    )


@pytest.mark.parametrize(
    "start,end,replacement",
    [
        (-1, 1, b"x"),
        (2, 1, b"x"),
        (0, 9, b"x"),
        (True, 2, b"x"),
        (0, False, b"x"),
        (0, 1, "x"),
        (0, 1, bytearray(b"x")),
    ],
)
def test_invalid_spans_fail_closed(start: object, end: object, replacement: object) -> None:
    core = _core()
    with pytest.raises(core.WritebackRejected):
        core.apply_byte_edits(b"abc", (core.ByteEdit(start, end, replacement),))


def test_output_size_is_bounded() -> None:
    core = _core()
    with pytest.raises(core.WritebackRejected) as error:
        core.apply_byte_edits(b"abc", (core.ByteEdit(1, 2, b"long"),), max_bytes=5)
    assert error.value.reason == core.WritebackReason.LIMIT_EXCEEDED
    assert core.apply_byte_edits(b"abc", (core.ByteEdit(1, 2, b"XYZ"),), max_bytes=5) == b"aXYZc"
    with pytest.raises(core.WritebackRejected):
        core.apply_byte_edits(b"too long", (core.ByteEdit(0, 8, b""),), max_bytes=5)


@given(
    prefix=st.binary(max_size=40),
    old=st.binary(max_size=40),
    suffix=st.binary(max_size=40),
    replacement=st.binary(max_size=40),
)
def test_arbitrary_byte_complement_is_preserved(
    prefix: bytes,
    old: bytes,
    suffix: bytes,
    replacement: bytes,
) -> None:
    core = _core()
    original = prefix + old + suffix
    assert (
        core.apply_byte_edits(
            original,
            (
                core.ByteEdit(
                    len(prefix),
                    len(prefix) + len(old),
                    replacement,
                ),
            ),
        )
        == prefix + replacement + suffix
    )
