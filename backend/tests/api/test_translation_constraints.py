"""Closed maximum-length mutation HTTP contracts."""

from __future__ import annotations

import importlib
import importlib.util
from types import ModuleType
from uuid import uuid4

import pytest
from pydantic import ValidationError


def _constraint_schemas() -> ModuleType:
    module_name = "verboflex.schemas.translation_constraints"
    assert importlib.util.find_spec(module_name) is not None
    return importlib.import_module(module_name)


@pytest.mark.parametrize("max_chars", [0, 1_048_576])
def test_constraint_schema_accepts_exact_inclusive_maximum_bounds(max_chars: int) -> None:
    schemas = _constraint_schemas()

    request = schemas.PutTranslationConstraintRequest.model_validate(
        {"max_chars": max_chars, "expected_version": 0}
    )

    assert request.model_dump() == {
        "max_chars": max_chars,
        "expected_version": 0,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"expected_version": 0},
        {"max_chars": 1},
        {"max_chars": None, "expected_version": 0},
        {"max_chars": 1.0, "expected_version": 0},
        {"max_chars": True, "expected_version": 0},
        {"max_chars": "1", "expected_version": 0},
        {"max_chars": -1, "expected_version": 0},
        {"max_chars": 1_048_577, "expected_version": 0},
        {"max_chars": 1, "expected_version": None},
        {"max_chars": 1, "expected_version": 0.0},
        {"max_chars": 1, "expected_version": False},
        {"max_chars": 1, "expected_version": "0"},
        {"max_chars": 1, "expected_version": -1},
        {"max_chars": 1, "expected_version": 0, "status": "client-owned"},
    ],
)
def test_constraint_put_schema_rejects_missing_null_coerced_bound_and_extra_payloads(
    payload: dict[str, object],
) -> None:
    schemas = _constraint_schemas()

    with pytest.raises(ValidationError):
        schemas.PutTranslationConstraintRequest.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"expected_version": None},
        {"expected_version": 1.0},
        {"expected_version": True},
        {"expected_version": "1"},
        {"expected_version": -1},
        {"expected_version": 1, "max_chars": 8},
    ],
)
def test_constraint_delete_schema_rejects_inexact_version_and_extra_payloads(
    payload: dict[str, object],
) -> None:
    schemas = _constraint_schemas()

    with pytest.raises(ValidationError):
        schemas.DeleteTranslationConstraintRequest.model_validate(payload)


def test_constraint_projection_preserves_zero_no_limit_and_exact_group_precision() -> None:
    schemas = _constraint_schemas()
    group_id = uuid4()
    equal_value_id = uuid4()
    over_value_id = uuid4()
    no_limit_value_id = uuid4()

    projection = schemas.TranslationConstraintMutationResponse.model_validate(
        {
            "translation_group_id": group_id,
            "language": "it",
            "base_language": "en",
            "explicit_maximum": 0,
            "version": 1,
            "violating_count": 1,
            "total_count": 3,
            "values": [
                {
                    "id": equal_value_id,
                    "language": "it",
                    "constraint": {
                        "actual": 0,
                        "maximum": 0,
                        "source": "language_override",
                        "status": "within_limit",
                        "overage": 0,
                    },
                    "approval_eligible": True,
                    "submission_eligible": True,
                },
                {
                    "id": over_value_id,
                    "language": "it",
                    "constraint": {
                        "actual": 2,
                        "maximum": 0,
                        "source": "language_override",
                        "status": "over_limit",
                        "overage": 2,
                    },
                    "approval_eligible": False,
                    "submission_eligible": False,
                },
                {
                    "id": no_limit_value_id,
                    "language": "en",
                    "constraint": {
                        "actual": 0,
                        "maximum": None,
                        "source": "none",
                        "status": "no_max",
                        "overage": None,
                    },
                    "approval_eligible": True,
                    "submission_eligible": True,
                },
            ],
        }
    ).model_dump()

    assert projection["explicit_maximum"] == 0
    assert projection["violating_count"] == 1
    assert projection["total_count"] == 3
    assert projection["values"][0]["constraint"] == {
        "actual": 0,
        "maximum": 0,
        "source": "language_override",
        "status": "within_limit",
        "overage": 0,
    }
    assert projection["values"][2]["constraint"] == {
        "actual": 0,
        "maximum": None,
        "source": "none",
        "status": "no_max",
        "overage": None,
    }


def test_constraint_schema_uses_visible_character_vocabulary() -> None:
    schemas = _constraint_schemas()
    description = schemas.PutTranslationConstraintRequest.model_json_schema()["properties"][
        "max_chars"
    ]["description"].casefold()

    assert "visible character" in description
    assert all(term not in description for term in ("byte", "code point", "utf"))
