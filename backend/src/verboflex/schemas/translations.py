"""Closed public contracts for translation search and grouped detail."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from verboflex.core.text import StorableText
from verboflex.localization.importing.core import MAX_CANONICAL_STRUCTURE_NODES

LanguageCode = Annotated[
    str,
    Field(
        min_length=2,
        max_length=64,
        pattern=r"^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$",
    ),
]
BoundedText = Annotated[StorableText, Field(max_length=1_048_576)]


class ClosedTranslationModel(BaseModel):
    """Forbid accidental public fields across every translation projection."""

    model_config = ConfigDict(extra="forbid")


class TranslationSearchQuery(ClosedTranslationModel):
    """Five exact filters plus one fixed page-size cursor envelope."""

    q: Annotated[StorableText | None, Field(max_length=256)] = None
    product_id: UUID | None = None
    language: LanguageCode | None = None
    state: Literal["draft", "approved", "rejected"] | None = None
    violation: Literal["over_limit", "within_limit", "no_max"] | None = None
    work_status: Literal["needs_translation", "needs_review", "source_changed"] | None = None
    deleted: Literal["active", "deleted", "all"] = "active"
    page_size: Literal[50] = 50
    cursor: Annotated[str | None, Field(min_length=1, max_length=2048)] = None

    @field_validator("page_size", mode="before")
    @classmethod
    def normalize_http_page_size(cls, value: object) -> object:
        """Accept the exact query-string spelling of the fixed integer contract."""
        return 50 if value == "50" else value


class TranslationProductOptionResponse(ClosedTranslationModel):
    id: UUID
    name: Annotated[str, Field(min_length=1, max_length=120)]


class TranslationLanguageOptionResponse(ClosedTranslationModel):
    code: LanguageCode
    label: Annotated[str, Field(min_length=1, max_length=128)]


class TranslationOptionsResponse(ClosedTranslationModel):
    products: Annotated[list[TranslationProductOptionResponse], Field(max_length=500)]
    languages: Annotated[list[TranslationLanguageOptionResponse], Field(max_length=500)]


class TranslationSummaryProvenanceResponse(ClosedTranslationModel):
    """One bounded last-known locator for a result group's leading member."""

    repository_name: Annotated[str, Field(min_length=1, max_length=201)]
    branch: Annotated[str, Field(min_length=1, max_length=255)]
    path: Annotated[str, Field(min_length=1, max_length=4096)]


class PendingTranslationSummaryResponse(ClosedTranslationModel):
    version: Annotated[int, Field(ge=1, le=9_007_199_254_740_991)]
    state: Literal["draft", "approved", "rejected"]
    reconciliation_required: bool
    target_branch: str | None = None
    target_integrated: bool = False
    value_count: Annotated[int, Field(ge=1, le=10_000)]


class TranslationGroupSummaryResponse(ClosedTranslationModel):
    id: UUID
    product_id: UUID
    product_name: Annotated[str, Field(min_length=1, max_length=120)]
    raw_key: Annotated[str, Field(min_length=1, max_length=1_048_576)]
    language: LanguageCode
    language_label: Annotated[str, Field(min_length=1, max_length=128)]
    rank: Annotated[int, Field(ge=0, le=3)]
    source_text: BoundedText | None
    source_language: LanguageCode | None
    translated_text: BoundedText | None
    selector_kinds: Annotated[
        list[
            Literal[
                "scalar",
                "android_quantity",
                "android_array_item",
                "qt_numerus",
                "qt_length_variant",
                "json_path",
            ]
        ],
        Field(min_length=1, max_length=6),
    ]
    provenance: TranslationSummaryProvenanceResponse | None
    value_count: Annotated[int, Field(ge=1)]
    over_limit_count: Annotated[int, Field(ge=0)]
    within_limit_count: Annotated[int, Field(ge=0)]
    no_max_count: Annotated[int, Field(ge=0)]
    states: Annotated[
        list[Literal["draft", "approved", "rejected"]],
        Field(min_length=1, max_length=3),
    ]
    state_summary: Literal["draft", "approved", "rejected", "mixed"]
    has_over_limit: bool
    has_no_max: bool
    is_deleted: bool
    pending_change: PendingTranslationSummaryResponse | None
    comment_count: Annotated[int, Field(ge=0)]


class TranslationSearchPageResponse(ClosedTranslationModel):
    items: Annotated[list[TranslationGroupSummaryResponse], Field(max_length=50)]
    next_cursor: Annotated[str | None, Field(min_length=1, max_length=2048)] = None


class TranslationConstraintProjectionResponse(ClosedTranslationModel):
    actual: Annotated[int, Field(ge=0)]
    maximum: Annotated[int | None, Field(ge=0, le=1_048_576)]
    source: Literal["none", "base_default", "language_override"]
    status: Literal["no_max", "within_limit", "over_limit"]
    overage: Annotated[int | None, Field(ge=0)]


class TranslationProvenanceResponse(ClosedTranslationModel):
    repository_id: UUID
    repository_name: Annotated[str, Field(min_length=1, max_length=201)]
    repository_side: Literal["direct", "keys", "translations"]
    branch: Annotated[str, Field(min_length=1, max_length=255)]
    path: Annotated[str, Field(min_length=1, max_length=4096)]
    format: Literal["android_xml", "qt_ts", "json", "ios_strings", "xliff"]
    commit_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    execution_id: UUID
    line: Annotated[int | None, Field(ge=1, le=2_147_483_647)]
    column: Annotated[int | None, Field(ge=1, le=2_147_483_647)]


class TranslationSelectorFieldResponse(ClosedTranslationModel):
    name: Annotated[str, Field(min_length=1, max_length=128)]
    value: BoundedText | int | bool | Annotated[list[BoundedText | int], Field(max_length=4096)]


class TranslationHistoryResponse(ClosedTranslationModel):
    revision_number: Annotated[int, Field(ge=1)]
    revision_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    review_state: Literal["draft", "approved", "rejected"]
    is_deleted: bool
    created_at: datetime
    commit_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    execution_id: UUID


class TranslationValueResponse(ClosedTranslationModel):
    id: UUID
    selector_version: Literal[1]
    selector_kind: Literal[
        "scalar",
        "android_quantity",
        "android_array_item",
        "qt_numerus",
        "qt_length_variant",
        "json_path",
    ]
    selector_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    selector_fields: Annotated[list[TranslationSelectorFieldResponse], Field(max_length=128)] | None
    history: Annotated[list[TranslationHistoryResponse], Field(max_length=50)]
    history_has_more: bool
    source_text: BoundedText | None
    translated_text: BoundedText | None
    display_text: BoundedText
    structure: Annotated[list[object], Field(max_length=MAX_CANONICAL_STRUCTURE_NODES)]
    review_state: Literal["draft", "approved", "rejected"]
    grapheme_count: Annotated[int, Field(ge=0)]
    constraint: TranslationConstraintProjectionResponse
    is_deleted: bool
    deleted_at: datetime | None
    provenance: TranslationProvenanceResponse | None
    source_value_id: UUID | None = None
    source_resolution: (
        Literal["embedded", "matched", "unmatched", "ambiguous", "unavailable"] | None
    ) = None
    source_comparison: TranslationSourceComparisonResponse | None = None


class TranslationSourceComparisonResponse(ClosedTranslationModel):
    source_value_id: UUID
    origin: Literal["embedded", "base_language"]
    previous_revision_number: Annotated[int, Field(ge=1)]
    current_revision_number: Annotated[int, Field(ge=1)]
    changed: bool
    previous_text: Annotated[str, Field(max_length=4096)]
    current_text: Annotated[str, Field(max_length=4096)]
    previous_truncated: bool
    current_truncated: bool
    previous_commit_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    current_commit_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    previous_execution_id: UUID
    current_execution_id: UUID


class TranslationSourceContextResponse(ClosedTranslationModel):
    source_value_id: UUID
    origin: Literal["embedded", "base_language"]
    language: LanguageCode | None
    selector_kind: Literal[
        "scalar",
        "android_quantity",
        "android_array_item",
        "qt_numerus",
        "qt_length_variant",
        "json_path",
    ]
    selector_fields: Annotated[list[TranslationSelectorFieldResponse], Field(max_length=128)] | None
    source_text: BoundedText | None
    provenance: TranslationProvenanceResponse | None
    source_comparison: TranslationSourceComparisonResponse | None


class PendingTranslationValueResponse(ClosedTranslationModel):
    translation_value_id: UUID
    selector_version: Literal[1]
    selector_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    basis_revision_number: Annotated[int, Field(ge=1)]
    basis_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    text: BoundedText
    grapheme_count: Annotated[int, Field(ge=0)]
    maximum: Annotated[int | None, Field(ge=0, le=1_048_576)]
    is_over_limit: bool
    approval_eligible: bool
    submission_eligible: bool


class PendingTranslationDetailResponse(ClosedTranslationModel):
    version: Annotated[int, Field(ge=1, le=9_007_199_254_740_991)]
    state: Literal["draft", "approved", "rejected"]
    reconciliation_required: bool
    target_branch: str | None = None
    target_integrated: bool = False
    updated_by: UUID
    updated_at: datetime
    values: Annotated[
        list[PendingTranslationValueResponse],
        Field(min_length=1, max_length=10_000),
    ]


class TranslationGroupDetailResponse(ClosedTranslationModel):
    id: UUID
    product_id: UUID
    product_name: Annotated[str, Field(min_length=1, max_length=120)]
    raw_key: Annotated[str, Field(min_length=1, max_length=1_048_576)]
    language: LanguageCode
    language_label: Annotated[str, Field(min_length=1, max_length=128)]
    base_language: LanguageCode | None
    explicit_maximum: Annotated[int | None, Field(ge=0, le=1_048_576)]
    constraint_version: Annotated[int | None, Field(ge=1)]
    base_maximum: Annotated[int | None, Field(ge=0, le=1_048_576)]
    states: Annotated[
        list[Literal["draft", "approved", "rejected"]],
        Field(min_length=1, max_length=3),
    ]
    state_summary: Literal["draft", "approved", "rejected", "mixed"]
    is_deleted: bool
    values: Annotated[list[TranslationValueResponse], Field(min_length=1, max_length=10_000)]
    pending_change: PendingTranslationDetailResponse | None
    comment_count: Annotated[int, Field(ge=0)]
    mutation_eligible: bool
    review_eligible: bool
    approval_commits_enabled: bool = False
    source_context: (
        Annotated[list[TranslationSourceContextResponse], Field(max_length=10_000)] | None
    ) = None


class TranslationErrorResponse(ClosedTranslationModel):
    detail: Literal[
        "Invalid translation cursor",
        "Translation unavailable",
        "Translation search unavailable",
    ]
