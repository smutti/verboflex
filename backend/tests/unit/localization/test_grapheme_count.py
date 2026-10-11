"""Contract tests for the authoritative visible-text grapheme counter."""

from importlib import import_module
from types import ModuleType
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

EXPECTED_ALGORITHM_VERSION = "regex==2026.9.3;uax29=extended_grapheme_clusters"


def _graphemes_module() -> ModuleType:
    """Load the public module lazily so RED fails inside the focused tests."""
    return import_module("verboflex.localization.graphemes")


def _grapheme_count(display_text: str) -> int:
    function: Any = _graphemes_module().grapheme_count
    return function(display_text)


@pytest.mark.parametrize(
    ("display_text", "expected"),
    [
        pytest.param("", 0, id="empty"),
        pytest.param("VerboFlex", 9, id="ascii"),
        pytest.param("\u00e9", 1, id="composed-accent"),
        pytest.param("e\u0301", 1, id="decomposed-accent"),
        pytest.param("\U0001f44d\U0001f3fd", 1, id="emoji-modifier"),
        pytest.param(
            "\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466", 1, id="emoji-zwj-family"
        ),
        pytest.param("\U0001f1ee\U0001f1f9", 1, id="regional-indicator-flag"),
        pytest.param("\r\n", 1, id="crlf"),
        pytest.param("\u05e2\u05d1\u05e8\u05d9\u05ea", 5, id="rtl"),
        pytest.param("first\nsecond", 12, id="multiline"),
        pytest.param("Save & continue", 15, id="markup-free-display-text"),
    ],
)
def test_counts_uax29_extended_grapheme_clusters(
    display_text: str,
    expected: int,
) -> None:
    assert _grapheme_count(display_text) == expected


def test_adjacent_clusters_remain_separate() -> None:
    display_text = "e\u0301\U0001f44d\U0001f3fd\U0001f1ee\U0001f1f9A\r\nB"

    assert _grapheme_count(display_text) == 6


@given(
    st.lists(
        st.sampled_from(
            (
                "A",
                "\u00e9",
                "e\u0301",
                "\U0001f44d\U0001f3fd",
                "\U0001f469\u200d\U0001f4bb",
                "\U0001f1ee\U0001f1f9",
                "\u05e9",
                "\r\n",
            )
        ),
        max_size=128,
    )
)
def test_count_is_additive_for_independent_visible_clusters(clusters: list[str]) -> None:
    assert _grapheme_count("".join(clusters)) == len(clusters)


def test_count_does_not_normalize_display_text() -> None:
    composed = "\u00e9"
    decomposed = "e\u0301"

    assert composed != decomposed
    assert composed.encode() != decomposed.encode()
    assert _grapheme_count(composed) == _grapheme_count(decomposed) == 1
    assert composed == "\u00e9"
    assert decomposed == "e\u0301"


@pytest.mark.parametrize(
    ("display_text", "maximum", "expected_overage"),
    [
        pytest.param("", 0, 0, id="zero-allows-empty"),
        pytest.param("abc", 3, 0, id="equal-is-within"),
        pytest.param("abcd", 3, 1, id="one-over"),
    ],
)
def test_count_is_an_exact_nonnegative_integer_at_limit_boundaries(
    display_text: str,
    maximum: int,
    expected_overage: int,
) -> None:
    actual = _grapheme_count(display_text)

    assert type(actual) is int
    assert actual >= 0
    assert max(actual - maximum, 0) == expected_overage


def test_counting_multiple_values_preserves_caller_order() -> None:
    display_texts = ("two", "e\u0301", "\U0001f469\u200d\U0001f4bb", "")

    assert tuple(_grapheme_count(text) for text in display_texts) == (3, 1, 1, 0)


@pytest.mark.parametrize("value", [None, b"text", 42, 3.5, ["text"]])
def test_rejects_absent_and_non_string_values(value: object) -> None:
    with pytest.raises(TypeError, match="display_text must be a str"):
        function: Any = _graphemes_module().grapheme_count
        function(value)


def test_exposes_the_exact_dependency_and_uax29_contract_version() -> None:
    module = _graphemes_module()

    assert module.GRAPHEME_ALGORITHM_VERSION == EXPECTED_ALGORITHM_VERSION
