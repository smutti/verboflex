"""Closed public contracts for complete translation proposal aggregates."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from verboflex.schemas.translations import BoundedText, LanguageCode

Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ExactVersion = Annotated[StrictInt, Field(ge=0, le=9_007_199_254_740_991)]
PositiveVersion = Annotated[StrictInt, Field(ge=1, le=9_007_199_254_740_991)]
ReviewState = Literal["draft", "approved", "rejected"]
ReviewActivityCursor = Annotated[str, Field(min_length=1, max_length=2_048)]


class ClosedReviewModel(BaseModel):
    """Reject accidental transport fields at the review boundary."""

    model_config = ConfigDict(extra="forbid")


class SaveTranslationProposalValueRequest(ClosedReviewModel):
    """One exact selector member and its imported edit basis."""

    translation_value_id: UUID
    selector_version: Literal[1]
    selector_digest: Sha256Digest
    basis_revision_number: PositiveVersion
    basis_digest: Sha256Digest
    proposed_text: BoundedText


class SaveTranslationProposalRequest(ClosedReviewModel):
    """Replace the complete key-language selector set under one version."""

    values: Annotated[
        list[SaveTranslationProposalValueRequest],
        Field(min_length=1, max_length=10_000),
    ]
    expected_version: ExactVersion


class ReviewTransitionRequest(ClosedReviewModel):
    """Request one exact closed state transition under optimistic authority."""

    target_state: ReviewState
    expected_version: PositiveVersion
    reason: Annotated[str, Field(max_length=4_096)] | None = None


class PublishedTranslationValueResponse(ClosedReviewModel):
    """Unchanged imported authority beside a pending proposal."""

    translation_value_id: UUID
    selector_version: Literal[1]
    selector_digest: Sha256Digest
    revision_number: PositiveVersion
    revision_digest: Sha256Digest
    text: BoundedText | None
    review_state: ReviewState


class PendingTranslationValueResponse(ClosedReviewModel):
    """Browser-authored value bound to one exact imported revision."""

    translation_value_id: UUID
    selector_version: Literal[1]
    selector_digest: Sha256Digest
    basis_revision_number: PositiveVersion
    basis_digest: Sha256Digest
    text: BoundedText
    grapheme_count: Annotated[StrictInt, Field(ge=0, le=1_048_576)]
    maximum: Annotated[StrictInt | None, Field(ge=0, le=1_048_576)]
    is_over_limit: bool
    approval_eligible: bool
    submission_eligible: bool


class ReviewActivityValueResponse(ClosedReviewModel):
    """One exact selector value captured in immutable review evidence."""

    translation_value_id: UUID
    selector_version: Literal[1]
    selector_digest: Sha256Digest
    basis_revision_number: PositiveVersion
    basis_digest: Sha256Digest
    text: BoundedText


class ReviewActivityEventResponse(ClosedReviewModel):
    """Complete bounded immutable evidence for one proposal change."""

    id: UUID
    translation_group_id: UUID
    language: LanguageCode
    kind: Literal["proposal_saved", "state_changed"]
    proposal_version: PositiveVersion
    from_state: ReviewState | None
    to_state: ReviewState | None
    before_values: Annotated[list[ReviewActivityValueResponse], Field(max_length=10_000)] | None
    after_values: Annotated[list[ReviewActivityValueResponse], Field(max_length=10_000)] | None
    reason: Annotated[str, Field(max_length=4_096)] | None
    comment_id: UUID | None
    actor_id: UUID
    created_at: datetime


class TranslationProposalActivityResponse(ReviewActivityEventResponse):
    """Latest immutable evidence associated with the proposal projection."""


class ReviewActivityResponse(ReviewActivityEventResponse):
    """One event in the complete review activity collection."""


class ReviewActivityPageResponse(ClosedReviewModel):
    """One fixed newest-first page of immutable review activity."""

    items: Annotated[list[ReviewActivityResponse], Field(max_length=20)]
    next_cursor: ReviewActivityCursor | None = None


class TranslationProposalResponse(ClosedReviewModel):
    """Fresh complete imported-plus-pending aggregate projection."""

    translation_group_id: UUID
    language: LanguageCode
    version: PositiveVersion
    state: ReviewState
    reconciliation_required: bool
    target_branch: str | None = None
    target_integrated: bool = False
    published: Annotated[
        list[PublishedTranslationValueResponse], Field(min_length=1, max_length=10_000)
    ]
    pending: Annotated[
        list[PendingTranslationValueResponse], Field(min_length=1, max_length=10_000)
    ]
    updated_by: UUID
    updated_at: datetime
    activity: TranslationProposalActivityResponse | None


class TranslationProposalConflictResponse(ClosedReviewModel):
    """Closed actionable comparison returned for version or basis conflicts."""

    detail: Literal[
        "Translation proposal conflict",
        "Translation proposal basis stale",
    ]
    attempted_version: ExactVersion
    attempted_values: Annotated[
        list[SaveTranslationProposalValueRequest],
        Field(min_length=1, max_length=10_000),
    ]
    latest: TranslationProposalResponse | None


class ReviewTransitionConflictResponse(ClosedReviewModel):
    """Fresh current proposal returned after a stale transition loses."""

    detail: Literal["Translation proposal conflict"]
    expected_version: PositiveVersion
    latest: TranslationProposalResponse


class TranslationProposalErrorResponse(ClosedReviewModel):
    detail: Literal[
        "Translation unavailable",
        "Translation action denied",
        "Invalid translation proposal input",
        "Translation proposal unavailable",
        "Translation proposal review blocked",
        "Invalid review activity cursor",
    ]
