"""Closed public contracts for maximum-length constraint mutations."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from verboflex.schemas.translations import (
    LanguageCode,
    TranslationConstraintProjectionResponse,
)

ExactMaximum = Annotated[
    StrictInt,
    Field(
        ge=0,
        le=1_048_576,
        description="Maximum number of visible characters allowed.",
    ),
]
ExactNonNegativeInt = Annotated[StrictInt, Field(ge=0)]
ExactPositiveInt = Annotated[StrictInt, Field(ge=1)]


class ClosedTranslationConstraintModel(BaseModel):
    """Forbid accidental request or response fields at the mutation boundary."""

    model_config = ConfigDict(extra="forbid")


class PutTranslationConstraintRequest(ClosedTranslationConstraintModel):
    """Create or replace one exact language-bound maximum."""

    max_chars: ExactMaximum
    expected_version: ExactNonNegativeInt


class DeleteTranslationConstraintRequest(ClosedTranslationConstraintModel):
    """Remove one explicit rule under exact optimistic authority."""

    expected_version: ExactNonNegativeInt


class TranslationConstraintMutationValueResponse(ClosedTranslationConstraintModel):
    """Fresh constraint and workflow eligibility for one canonical value."""

    id: UUID
    language: LanguageCode
    constraint: TranslationConstraintProjectionResponse
    approval_eligible: bool
    submission_eligible: bool


class TranslationConstraintMutationResponse(ClosedTranslationConstraintModel):
    """Fresh explicit rule and complete affected-value projection."""

    translation_group_id: UUID
    language: LanguageCode
    base_language: LanguageCode
    explicit_maximum: ExactMaximum | None
    version: ExactPositiveInt | None
    violating_count: ExactNonNegativeInt
    total_count: ExactNonNegativeInt
    values: Annotated[
        list[TranslationConstraintMutationValueResponse],
        Field(min_length=1, max_length=10_000),
    ]
