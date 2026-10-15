"""Bounded administrator configuration; exact text never acts as a language detector."""

from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from verboflex.schemas.translations import LanguageCode

SourceText = Annotated[str, Field(min_length=1, max_length=4096)]


class SourceFallbackWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: Annotated[int, Field(ge=0)]
    enabled: bool
    language: LanguageCode | None
    source_texts: Annotated[list[SourceText], Field(max_length=2000)]

    @model_validator(mode="after")
    def validate_sources(self) -> Self:
        if self.enabled and self.language is None:
            raise ValueError("Select a base language")
        if len(set(self.source_texts)) != len(self.source_texts):
            raise ValueError("Source texts must be unique")
        if any(not value.strip() or "\x00" in value for value in self.source_texts):
            raise ValueError("Source texts must contain visible text")
        if sum(len(value.encode("utf-8")) for value in self.source_texts) > 262144:
            raise ValueError("Source text selection is too large")
        return self


class SourceFallbackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    version: Annotated[int, Field(ge=0)]
    enabled: bool
    language: LanguageCode | None
    source_texts: Annotated[list[SourceText], Field(max_length=2000)]
    available_languages: Annotated[list[LanguageCode], Field(max_length=500)]
