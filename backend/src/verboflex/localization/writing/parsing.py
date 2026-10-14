"""Write-only inspection of shared MOKO files, without relaxing canonical imports."""

from verboflex.localization.importing.android_xml import AndroidXmlInspection, inspect_android_xml
from verboflex.localization.importing.core import CanonicalParseResult, CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.moko_layout import moko_layout


def inspect_writeback_snapshot(
    parser_input: CanonicalParserInput,
) -> CanonicalParseResult | AndroidXmlInspection:
    """Retain every occurrence when unrelated duplicates belong to a shared catalog.

    Code-backed imports select keys from a translations repository. That catalog
    can contain duplicate keys outside the selected product. The writer must
    preserve those occurrences and separately reject ambiguous edit targets.
    Malformed/unsupported content and ordinary canonical imports stay strict.
    """
    parsed = parse_canonical_snapshot(parser_input)
    if (
        parsed.issues
        and all(issue.code == "duplicate_key" for issue in parsed.issues)
        and parser_input.format == "android_xml"
        and parser_input.repository_side == "translations"
        and moko_layout(parser_input.path) is not None
    ):
        return inspect_android_xml(parser_input)
    return parsed
