"""Bounded product cards with imported repository coverage."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from verboflex.schemas.translations import ClosedTranslationModel, LanguageCode


class ProductWorkspaceQuery(ClosedTranslationModel):
    product_id: UUID | None = None
    q: str = Field(default="", max_length=120, pattern=r"^[^\x00]*$")
    page: int = Field(default=1, ge=1, le=1_000_000)


class ProductWorkspaceCoverage(ClosedTranslationModel):
    source_string_count: Annotated[int, Field(ge=0)]
    expected_translation_count: Annotated[int, Field(ge=0)]
    translated_count: Annotated[int, Field(ge=0)]
    missing_count: Annotated[int, Field(ge=0)]
    coverage_percent: Annotated[float, Field(ge=0, le=100)] | None
    language_count: Annotated[int, Field(ge=0)]
    languages: Annotated[list[LanguageCode], Field(max_length=6)]


class ProductWorkspaceCard(ClosedTranslationModel):
    id: UUID
    name: Annotated[str, Field(min_length=1, max_length=120)]
    coverage: ProductWorkspaceCoverage | None
    imported_scope_count: Annotated[int, Field(ge=0)]
    unimported_scope_count: Annotated[int, Field(ge=0)]
    last_imported_at: datetime | None


class ProductWorkspacePage(ClosedTranslationModel):
    items: Annotated[list[ProductWorkspaceCard], Field(max_length=24)]
    total: Annotated[int, Field(ge=0)]
    page: Annotated[int, Field(ge=1)]
    has_more: bool
