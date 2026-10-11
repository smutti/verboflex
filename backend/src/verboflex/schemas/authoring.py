"""Bounded authoring contracts shared by the UI and MCP."""

import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from verboflex.localization.preview.core import normalize_preview_locale

Version = Annotated[StrictInt, Field(ge=0, le=9_007_199_254_740_991)]
Text = Annotated[str, Field(max_length=65536)]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def database_text(cls, value: object) -> object:
        if isinstance(value, str) and any(c == "\x00" or 0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValueError("Invalid text")
        return value


class AuthoringForm(ClosedModel):
    form: Annotated[str, Field(max_length=16)] = "other"
    text: Text


class AuthoringInput(ClosedModel):
    scope_id: UUID
    expected_version: Version = 0
    execution_id: UUID
    file_position: Annotated[StrictInt, Field(ge=0, le=2147483647)]
    parent_key_id: UUID | None = None
    key: Annotated[str, Field(min_length=1, max_length=4096)]
    language: Annotated[str, Field(min_length=2, max_length=32)]
    kind: Literal["text", "plural"] = "text"
    source_text: Text = ""
    context: Annotated[str, Field(max_length=4096)] = ""
    disambiguation: Annotated[str, Field(max_length=4096)] = ""
    identity_kind: Literal["id", "source"] = "id"
    parents: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=256)]], Field(max_length=10)
    ] = []
    forms: Annotated[list[AuthoringForm], Field(min_length=1, max_length=6)]
    max_chars: Annotated[StrictInt, Field(ge=0, le=1048576)] | None = None

    @model_validator(mode="after")
    def consistent_forms(self) -> AuthoringInput:
        if normalize_preview_locale(self.language) != self.language:
            raise ValueError("Invalid language")
        if len({f.form for f in self.forms}) != len(self.forms):
            raise ValueError("Duplicate form")
        if self.kind == "text" and (len(self.forms) != 1 or self.forms[0].form != "other"):
            raise ValueError("Text requires one value")
        if any("\x00" in p or any(0xD800 <= ord(c) <= 0xDFFF for c in p) for p in self.parents):
            raise ValueError("Invalid path")
        if len(json.dumps(self.model_dump(mode="json"), ensure_ascii=False).encode()) > 1_000_000:
            raise ValueError("Draft is too large")
        return self


class AuthoringDestination(ClosedModel):
    scope_id: UUID
    execution_id: UUID
    file_position: int
    path: str
    format: str
    repository: str
    provider: str
    repository_side: str
    base_language: str
    languages: list[str]
    topology: str


class AuthoringDestinations(ClosedModel):
    items: list[AuthoringDestination]
    truncated: bool = False


class AuthoringResponse(ClosedModel):
    id: UUID
    version: int
    state: Literal["draft", "approved", "rejected"]
    input: AuthoringInput
    path: str
    format: str
    source_changed: bool
    updated_at: datetime


class AuthoringPage(ClosedModel):
    items: list[AuthoringResponse]
    next_after: UUID | None = None


class AuthoringReview(ClosedModel):
    expected_version: Version
    state: Literal["draft", "approved", "rejected"]


class PluralFormOption(ClosedModel):
    form: str
    label: str


class PluralFormsResponse(ClosedModel):
    profile: str
    forms: list[PluralFormOption]
