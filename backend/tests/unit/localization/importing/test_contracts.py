"""Frozen public contracts for complete canonical localization results."""

from __future__ import annotations

import importlib
import json
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, cast, get_args

import pytest
from sqlalchemy import inspect as sqlalchemy_inspect

from verboflex.localization.importing import core
from verboflex.localization.importing.registry import parse_canonical_snapshot

_FIXTURES = Path(__file__).parents[3] / "fixtures" / "localization" / "android"

_SELECTOR_KINDS = (
    "scalar",
    "android_quantity",
    "android_array_item",
    "qt_numerus",
    "qt_length_variant",
    "json_path",
)
_REVIEW_STATES = ("draft", "approved", "rejected")
_EFFECTIVE_CONSTRAINT_SOURCES = ("none", "base_default", "language_override")
_ISSUE_CODES = (
    "malformed_file",
    "ambiguous_structure",
    "unsupported_structure",
    "duplicate_key",
    "base_language_required",
)
_PUBLIC_EXPORTS = {
    "CanonicalFormat",
    "CanonicalIssue",
    "CanonicalLocator",
    "CanonicalParseResult",
    "CanonicalParser",
    "CanonicalParserInput",
    "CanonicalSelector",
    "CanonicalStructureNode",
    "CanonicalValue",
    "IssueCode",
    "RepositorySide",
    "ReviewState",
    "SelectorKind",
    "StructureKind",
    "canonical_issue_order",
    "canonical_selector_bytes",
    "canonical_selector_digest",
    "canonical_value_order",
    "parse_canonical_snapshot",
}
_MODEL_EXPORTS = {
    "EffectiveConstraintSource",
    "LocalizationScope",
    "ParseIssueCode",
    "ReviewState",
    "SelectorKind",
    "StagedTranslationValue",
    "TranslationConstraint",
    "TranslationKey",
    "TranslationParseIssue",
    "TranslationValue",
    "TranslationValueLocator",
    "TranslationValueRevision",
}


def _locator(**overrides: object) -> core.CanonicalLocator:
    values: dict[str, object] = {
        "format": "android_xml",
        "repository_side": "direct",
        "path": "app/src/main/res/values/strings.xml",
        "position": 0,
        "structural_address": ("resources", "string", 0),
        "line": 3,
        "column": 5,
    }
    values.update(overrides)
    return core.CanonicalLocator(**cast(Any, values))


def _value(
    logical_key: str,
    *,
    selector: core.CanonicalSelector | None = None,
    locator: core.CanonicalLocator | None = None,
) -> core.CanonicalValue:
    text = f"text:{logical_key}"
    return core.CanonicalValue(
        logical_key=logical_key,
        language="en-US",
        selector=selector or core.CanonicalSelector(kind="scalar", fields=()),
        source_text=text,
        translated_text=None,
        display_text=text,
        structure=(
            core.CanonicalStructureNode(kind="android_xml:string", fields=()),
            core.CanonicalStructureNode(
                kind="android_xml:text",
                fields=(("value", text),),
            ),
        ),
        locator=locator or _locator(),
    )


def _issue(**overrides: object) -> core.CanonicalIssue:
    values: dict[str, object] = {
        "code": "unsupported_structure",
        "repository_side": "direct",
        "path": "app/src/main/res/values/strings.xml",
        "message": "Unsupported localization structure.",
        "line": 3,
        "column": 5,
    }
    values.update(overrides)
    return core.CanonicalIssue(**cast(Any, values))


def test_selector_and_review_vocabularies_are_frozen_and_public() -> None:
    importing = importlib.import_module("verboflex.localization.importing")

    assert get_args(core.SelectorKind) == _SELECTOR_KINDS
    assert get_args(core.ReviewState) == _REVIEW_STATES
    assert core.SELECTOR_SCHEMA_VERSION == 1
    assert core.STRUCTURE_SCHEMA_VERSION == 1
    assert _PUBLIC_EXPORTS.issubset(set(dir(importing)))

    for kind in _SELECTOR_KINDS:
        assert core.CanonicalSelector(kind=cast(Any, kind), fields=()).schema_version == 1

    with pytest.raises(ValueError, match="selector rejected"):
        core.CanonicalSelector(kind=cast(Any, "plural"), fields=())
    with pytest.raises(ValueError, match="selector rejected"):
        core.CanonicalSelector(kind="scalar", fields=(), schema_version=2)


def test_canonical_models_export_closed_lowercase_vocabularies() -> None:
    models = importlib.import_module("verboflex.models")

    assert _MODEL_EXPORTS <= set(models.__all__)
    assert tuple(member.value for member in models.SelectorKind) == _SELECTOR_KINDS
    assert tuple(member.value for member in models.ReviewState) == _REVIEW_STATES
    assert tuple(member.value for member in models.EffectiveConstraintSource) == (
        _EFFECTIVE_CONSTRAINT_SOURCES
    )
    assert tuple(member.value for member in models.ParseIssueCode) == _ISSUE_CODES
    assert get_args(core.SelectorKind) == tuple(member.value for member in models.SelectorKind)
    assert get_args(core.ReviewState) == tuple(member.value for member in models.ReviewState)
    assert get_args(core.IssueCode) == tuple(member.value for member in models.ParseIssueCode)

    for vocabulary in (
        models.SelectorKind,
        models.ReviewState,
        models.EffectiveConstraintSource,
        models.ParseIssueCode,
    ):
        for member in vocabulary:
            assert str(member) == member.value
        with pytest.raises(ValueError):
            vocabulary("unknown")


def test_canonical_model_relationships_preserve_semantic_ownership() -> None:
    models = importlib.import_module("verboflex.models")

    mapping_scopes = sqlalchemy_inspect(models.ProductRepositoryMapping).relationships[
        "localization_scopes"
    ]
    assert mapping_scopes.viewonly is True
    assert {
        (local.name, remote.name) for local, remote in mapping_scopes.local_remote_pairs
    } == {
        ("revision_id", "current_revision_id"),
        ("id", "current_mapping_id"),
        ("identity_key", "mapping_identity_key"),
    }

    scope_relationships = sqlalchemy_inspect(models.LocalizationScope).relationships
    assert {"current_mapping", "translation_keys"} <= set(scope_relationships)
    assert scope_relationships["current_mapping"].viewonly is True
    assert scope_relationships["translation_keys"].passive_deletes is True

    key_relationships = sqlalchemy_inspect(models.TranslationKey).relationships
    assert {"scope", "values", "constraints"} <= set(key_relationships)
    assert key_relationships["values"].passive_deletes is True
    assert key_relationships["constraints"].passive_deletes is True

    value_relationships = sqlalchemy_inspect(models.TranslationValue).relationships
    assert {"key", "revisions", "locator"} <= set(value_relationships)
    assert value_relationships["revisions"].passive_deletes is True
    assert value_relationships["locator"].uselist is False
    assert value_relationships["locator"].passive_deletes is True

    constraint_relationships = sqlalchemy_inspect(models.TranslationConstraint).relationships
    assert set(constraint_relationships) >= {"key", "created_by_user", "updated_by_user"}


def test_selector_bytes_are_sorted_compact_typed_and_sequence_ordered() -> None:
    selector = core.CanonicalSelector(
        kind="qt_length_variant",
        fields=(("priority", 2), ("context", "checkout"), ("form_indexes", (2, 1))),
    )
    equivalent = core.CanonicalSelector(
        kind="qt_length_variant",
        fields=(("form_indexes", (2, 1)), ("context", "checkout"), ("priority", 2)),
    )
    reordered_sequence = replace(
        selector,
        fields=(("priority", 2), ("context", "checkout"), ("form_indexes", (1, 2))),
    )
    changed_type = replace(
        selector,
        fields=(("priority", "2"), ("context", "checkout"), ("form_indexes", (2, 1))),
    )

    expected = (
        b'{"fields":{"context":"checkout","form_indexes":[2,1],"priority":2},'
        b'"kind":"qt_length_variant","version":1}'
    )
    assert core.canonical_selector_bytes(selector) == expected
    assert core.canonical_selector_bytes(equivalent) == expected
    assert core.canonical_selector_digest(selector) == core.canonical_selector_digest(equivalent)
    assert core.canonical_selector_digest(selector) != core.canonical_selector_digest(
        reordered_sequence
    )
    assert core.canonical_selector_digest(selector) != core.canonical_selector_digest(changed_type)
    assert len(core.canonical_selector_digest(selector)) == 64


@pytest.mark.parametrize(
    "fields_value",
    (
        (("duplicate", 1), ("duplicate", 2)),
        (("", 1),),
        (("float", 1.5),),
        (("mixed", (1, "two")),),
        (("mapping", {"nested": "payload"}),),
        [("not_a_tuple", 1)],
    ),
)
def test_selector_fields_reject_noncanonical_or_ambiguous_shapes(fields_value: object) -> None:
    with pytest.raises(ValueError, match="selector rejected"):
        core.CanonicalSelector(kind="scalar", fields=cast(Any, fields_value))


def test_structure_nodes_use_an_exact_versioned_allowlist_and_ordered_fields() -> None:
    node = core.CanonicalStructureNode(
        kind="android_xml:string",
        fields=(("translatable", True), ("formatted", False)),
    )

    assert node.to_mapping() == {
        "fields": [
            {"name": "translatable", "value": True},
            {"name": "formatted", "value": False},
        ],
        "kind": "android_xml:string",
        "version": 1,
    }

    with pytest.raises(ValueError, match="structure node rejected"):
        core.CanonicalStructureNode(kind="text", fields=())
    with pytest.raises(ValueError, match="structure node rejected"):
        core.CanonicalStructureNode(kind=cast(Any, "android_xml:unknown"), fields=())
    with pytest.raises(ValueError, match="structure node rejected"):
        core.CanonicalStructureNode(kind="android_xml:text", fields=(), schema_version=2)
    with pytest.raises(ValueError, match="structure node rejected"):
        core.CanonicalStructureNode(
            kind="android_xml:text",
            fields=(("value", "one"), ("value", "two")),
        )


@pytest.mark.parametrize(
    "overrides",
    (
        {"format": "unknown"},
        {"repository_side": "source"},
        {"path": "/absolute/strings.xml"},
        {"path": "app/../strings.xml"},
        {"position": -1},
        {"position": True},
        {"structural_address": ()},
        {"structural_address": ("resources", -1)},
        {"line": 0},
        {"column": 2_147_483_648},
    ),
)
def test_locator_rejects_invalid_path_and_bounded_coordinates(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="locator rejected"):
        _locator(**overrides)


def test_value_rejects_invalid_identity_locale_and_lossless_structure() -> None:
    valid = _value("welcome.title")
    assert valid.language == "en-US"

    for changes in (
        {"logical_key": ""},
        {"logical_key": "bad\x00key"},
        {"language": "en_us"},
        {"language": "default"},
        {"structure": ()},
        {"structure": (core.CanonicalStructureNode(kind="qt_ts:text", fields=(("value", "x"),)),)},
    ):
        with pytest.raises(ValueError, match="canonical value rejected"):
            replace(valid, **cast(Any, changes))


def test_result_rejects_duplicate_identity_and_noncanonical_value_order() -> None:
    first = _value("alpha")
    last = _value("zulu", locator=_locator(position=1))

    assert core.CanonicalParseResult(values=(first, last)).values == (first, last)

    with pytest.raises(ValueError, match="canonical result rejected"):
        core.CanonicalParseResult(values=(last, first))

    duplicate_at_a_new_locator = replace(
        first,
        locator=_locator(path="moved/res/values/strings.xml", position=99),
    )
    with pytest.raises(ValueError, match="canonical result rejected"):
        core.CanonicalParseResult(values=(first, duplicate_at_a_new_locator))


def test_issue_contract_is_closed_bounded_source_free_and_ordered() -> None:
    keys_issue = _issue(repository_side="keys", path="keys/a.xml", line=None, column=None)
    translations_issue = _issue(
        repository_side="translations",
        path="translations/a.xml",
        line=None,
        column=None,
    )

    assert core.CanonicalParseResult(issues=(keys_issue, translations_issue)).issues == (
        keys_issue,
        translations_issue,
    )
    with pytest.raises(ValueError, match="canonical result rejected"):
        core.CanonicalParseResult(issues=(translations_issue, keys_issue))

    for changes in (
        {"code": "parser_exception"},
        {"repository_side": "source"},
        {"path": "../secret.xml"},
        {"message": ""},
        {"message": "x" * 257},
        {"message": "unsafe\x00payload"},
        {"line": 0},
        {"column": 2_147_483_648},
    ):
        with pytest.raises(ValueError, match="canonical issue rejected"):
            _issue(**changes)

    with pytest.raises(TypeError):
        core.CanonicalIssue(
            code="malformed_file",
            repository_side="direct",
            path="safe.xml",
            message="Malformed file.",
            source_fragment="secret",
        )
    with pytest.raises(TypeError):
        core.CanonicalIssue(
            code="malformed_file",
            repository_side="direct",
            path="safe.xml",
            message="Malformed file.",
            exception=RuntimeError("secret"),
        )
    assert {field.name for field in fields(core.CanonicalIssue)} == {
        "code",
        "repository_side",
        "path",
        "message",
        "line",
        "column",
    }
    assert not hasattr(keys_issue, "__dict__")


def test_android_scalar_matches_the_hand_authored_byte_stable_manifest() -> None:
    parser_input = core.CanonicalParserInput(
        format="android_xml",
        repository_side="direct",
        path="app/src/main/res/values/strings.xml",
        content=(_FIXTURES / "scalar.xml").read_bytes(),
        layout_identity="app/src/main/res",
        layout_version=1,
        base_language="en_US",
    )
    result = parse_canonical_snapshot(parser_input)
    expected_bytes = (_FIXTURES / "scalar.expected.json").read_bytes()

    assert result.issues == ()
    assert result.to_mapping() == json.loads(expected_bytes)
    assert (
        json.dumps(
            result.to_mapping(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
        == expected_bytes
    )
