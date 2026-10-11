"""Project terminology contracts."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field, StrictBool, model_validator

from verboflex.localization.preview.core import normalize_preview_locale
from verboflex.schemas.authoring import ClosedModel, Version


class GlossaryInput(ClosedModel):
    expected_version: Version = 0
    source_language: Annotated[str, Field(min_length=2, max_length=32)]
    target_language: Annotated[str, Field(min_length=2, max_length=32)]
    source_term: Annotated[str, Field(min_length=1, max_length=256)]
    target_term: Annotated[str, Field(min_length=1, max_length=256)]
    forbidden: StrictBool = False
    case_sensitive: StrictBool = False
    note: Annotated[str, Field(max_length=1000)] = ""

    @model_validator(mode="after")
    def terms(self) -> GlossaryInput:
        if any(
            normalize_preview_locale(v) != v for v in (self.source_language, self.target_language)
        ):
            raise ValueError("Invalid language")
        if not self.source_term.strip() or not self.target_term.strip():
            raise ValueError("Term must contain text")
        return self


class GlossaryResponse(GlossaryInput):
    id: UUID
    version: int
    updated_at: datetime


class GlossaryPage(ClosedModel):
    items: list[GlossaryResponse]
    next_after: UUID | None = None


class GlossaryMatchQuery(ClosedModel):
    source_language: Annotated[str, Field(min_length=2, max_length=32)]
    target_language: Annotated[str, Field(min_length=2, max_length=32)]
    source_text: Annotated[str, Field(max_length=4096)]

    @model_validator(mode="after")
    def languages(self) -> GlossaryMatchQuery:
        if any(
            normalize_preview_locale(v) != v for v in (self.source_language, self.target_language)
        ):
            raise ValueError("Invalid language")
        return self


class GlossaryMatches(ClosedModel):
    items: list[GlossaryResponse]
    truncated: bool = False
