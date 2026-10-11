"""Bounded current-content suggestions; applying one never saves a proposal."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from verboflex.localization.preview.core import normalize_preview_locale
from verboflex.schemas.authoring import ClosedModel


class ReuseQuery(ClosedModel):
    source_text: Annotated[str, Field(min_length=1, max_length=4096)]
    source_language: Annotated[str, Field(min_length=2, max_length=32)]
    target_language: Annotated[str, Field(min_length=2, max_length=32)]
    format: Literal["android_xml", "qt_ts", "json", "ios_strings"]
    selector_kind: Literal[
        "scalar", "android_quantity", "android_array_item", "qt_numerus", "json_path"
    ]
    selector_form: Annotated[str, Field(max_length=16)] | None = None
    exclude_value_id: UUID | None = None
    fuzzy: bool = True

    @model_validator(mode="after")
    def language_pair(self) -> ReuseQuery:
        if any(
            normalize_preview_locale(v) != v for v in (self.source_language, self.target_language)
        ):
            raise ValueError("Invalid language")
        if self.selector_kind in {"android_quantity", "qt_numerus"} and self.selector_form is None:
            raise ValueError("Plural form is required")
        return self


class ReuseSuggestion(ClosedModel):
    source_value_id: UUID
    target_value_id: UUID
    group_id: UUID
    product_id: UUID
    product_name: str
    key: str
    source_text: str
    target_text: str
    source_language: str
    target_language: str
    match_percent: int
    origin: Literal["repository", "approved_draft"]
    proposal_version: int | None
    repository: str
    file: str
    digest: str


class ReusePage(ClosedModel):
    items: list[ReuseSuggestion]


class ReuseResolve(ClosedModel):
    query: ReuseQuery
    source_value_id: UUID
    target_value_id: UUID
    expected_digest: Annotated[str, Field(pattern="^[0-9a-f]{64}$")]
