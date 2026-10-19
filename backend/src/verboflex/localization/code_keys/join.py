"""Join code identities to real, independently parsed translation files."""

from dataclasses import dataclass, replace

from verboflex.localization.code_keys.catalog import CodeKeyCatalog
from verboflex.localization.importing.core import (
    CanonicalParseResult,
    CanonicalParserInput,
    canonical_selector_bytes,
)
from verboflex.localization.importing.registry import (
    parse_canonical_mapping_quarantining_duplicates,
)


@dataclass(frozen=True)
class CodeTranslationJoin:
    result: CanonicalParseResult
    missing_keys: tuple[str, ...] = ()
    orphan_keys: tuple[str, ...] = ()
    missing_base_keys: tuple[str, ...] = ()


def join_code_translations(
    catalog: CodeKeyCatalog, inputs: tuple[CanonicalParserInput, ...]
) -> CodeTranslationJoin:
    # Parse the translation repository as a complete localization dataset. Restore
    # its real mapping side immediately; code never enters a localization parser.
    if any(item.repository_side != "translations" for item in inputs):
        raise ValueError("Code catalog requires a separate translations repository")
    parsed = parse_canonical_mapping_quarantining_duplicates(
        tuple(replace(i, repository_side="direct") for i in inputs)
    )
    if parsed.issues:
        return CodeTranslationJoin(
            CanonicalParseResult(
                issues=tuple(
                    replace(issue, repository_side="translations") for issue in parsed.issues
                )
            )
        )
    base = inputs[0].base_language
    source = {
        (value.logical_key, canonical_selector_bytes(value.selector)): value.display_text
        for value in parsed.values
        if value.language == base
    }
    keys = set(catalog.keys)
    found = {value.logical_key for value in parsed.values}
    values = tuple(
        replace(
            value,
            source_text=source.get((value.logical_key, canonical_selector_bytes(value.selector))),
            locator=replace(value.locator, repository_side="translations"),
        )
        for value in parsed.values
        if value.logical_key in keys
    )
    return CodeTranslationJoin(
        result=CanonicalParseResult(values=values),
        missing_keys=tuple(sorted(keys - found)),
        orphan_keys=tuple(sorted(found - keys)),
        missing_base_keys=tuple(sorted(keys - {key for key, _ in source})),
    )
