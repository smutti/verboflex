"""Bounded canonical-key pages; previews are never proposal payloads."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from verboflex.schemas.translations import (
    ClosedTranslationModel,
    LanguageCode,
    PendingTranslationSummaryResponse,
    TranslationLanguageOptionResponse,
    TranslationSearchQuery,
)
from verboflex.services.translation_search import SelectorKind, StateFilter

Preview = Annotated[str, Field(max_length=1024)]


class TranslationKeySearchQuery(TranslationSearchQuery):
    """Conditions AND within a relevant locale; a match includes all visible siblings."""

    visible_languages: Annotated[list[LanguageCode] | None, Field(min_length=1, max_length=20)] = (
        None
    )

    @field_validator("visible_languages")
    @classmethod
    def unique_languages(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("visible languages must be unique")
        return value


class TranslationWorkspaceProvenance(ClosedTranslationModel):
    repository_side: Literal["direct", "keys", "translations"]
    format: Literal["android_xml", "qt_ts", "json", "ios_strings", "xliff"]
    repository_name: Preview
    branch: Preview
    path: Preview
    path_truncated: bool


class TranslationLanguageSlot(ClosedTranslationModel):
    """Complete aggregate facts. Imported states/limits exclude pending proposal state/limits.

    A fresh, complete, non-rejected proposal supplies effective text.
    effective_over_limit_count follows that same text selection. Empty imported
    targets can need translation; absent slots cannot be saved. Capability describes
    provenance/shape, while existing mutation endpoints still enforce user roles.
    """

    language: LanguageCode
    language_label: Annotated[str, Field(max_length=128)]
    kind: Literal["imported", "source_context", "absent"]
    group_id: UUID | None
    matches_filters: bool
    effective_text: Preview | None
    text_truncated: bool
    preview_kind: Literal["scalar", "aggregate", "context", "absent"]
    value_count: Annotated[int, Field(ge=0)]
    selector_kinds: Annotated[list[SelectorKind], Field(max_length=6)]
    states: Annotated[list[StateFilter], Field(max_length=3)]
    pending_change: PendingTranslationSummaryResponse | None
    comment_count: Annotated[int, Field(ge=0)]
    over_limit_count: Annotated[int, Field(ge=0)]
    effective_over_limit_count: Annotated[int, Field(ge=0)] = 0
    within_limit_count: Annotated[int, Field(ge=0)]
    no_max_count: Annotated[int, Field(ge=0)]
    is_deleted: bool
    source_changed: bool
    provenance: TranslationWorkspaceProvenance | None
    editable: bool
    edit_field: Literal["source_text", "translated_text"] | None
    read_only_reason: (
        Literal[
            "absent",
            "source_context",
            "deleted",
            "keys_repository",
            "unsupported_format",
            "unsupported_shape",
            "unavailable_provenance",
            "mixed_edit_fields",
        ]
        | None
    )


class TranslationKeySummary(ClosedTranslationModel):
    translation_key_id: UUID
    scope_id: UUID
    product_id: UUID
    product_name: Annotated[str, Field(max_length=120)]
    raw_key: Preview
    key_truncated: bool
    base_language: LanguageCode | None
    rank: Annotated[int, Field(ge=0, le=3)]
    source_text: Preview | None
    source_truncated: bool
    slots: Annotated[list[TranslationLanguageSlot], Field(max_length=20)]


class TranslationKeyPageResponse(ClosedTranslationModel):
    items: Annotated[list[TranslationKeySummary], Field(max_length=50)]
    next_cursor: Annotated[str | None, Field(max_length=2048)]
    visible_languages: Annotated[list[LanguageCode], Field(max_length=20)]
    available_languages: Annotated[list[TranslationLanguageOptionResponse], Field(max_length=500)]
    language_selection_limit: Literal[20] = 20
    default_selection_capped: bool
    available_languages_truncated: bool
