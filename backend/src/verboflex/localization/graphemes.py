"""Authoritative Unicode grapheme counting for canonical display text."""

import regex  # type: ignore[import-untyped]  # The approved package ships no type metadata.

GRAPHEME_ALGORITHM_VERSION = f"regex=={regex.__version__};uax29=extended_grapheme_clusters"

_GRAPHEME_PATTERN = regex.compile(r"\X")


def grapheme_count(display_text: str) -> int:
    """Count UAX #29 extended grapheme clusters in visible display text."""
    if not isinstance(display_text, str):
        raise TypeError("display_text must be a str")

    return sum(1 for _match in _GRAPHEME_PATTERN.finditer(display_text))
