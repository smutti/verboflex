"""Safe handling for the standard, declaration-only Qt TS doctype."""

from __future__ import annotations

import re

_STANDARD_QT_DOCTYPE = re.compile(r"<!DOCTYPE[ \t\r\n]+TS[ \t\r\n]*>")


def mask_standard_qt_doctype(text: str) -> str:
    """Mask one plain ``<!DOCTYPE TS>`` while preserving diagnostic line numbers.

    Entity declarations, internal subsets, external identifiers, repeated doctypes,
    and doctypes outside the XML prolog remain untouched so ``defusedxml`` rejects
    them with its existing fail-closed configuration.
    """
    marker = "<!DOCTYPE"
    start = text.find(marker)
    if start < 0:
        return text
    if text.find(marker, start + len(marker)) >= 0:
        return text
    match = _STANDARD_QT_DOCTYPE.match(text, start)
    if match is None:
        return text

    prefix = text[:start]
    stripped_prefix = prefix.strip()
    if stripped_prefix and not (
        stripped_prefix.startswith("<?xml") and stripped_prefix.endswith("?>")
    ):
        return text

    masked = "".join(character if character in {"\r", "\n"} else " " for character in match.group())
    return f"{text[:start]}{masked}{text[match.end() :]}"
