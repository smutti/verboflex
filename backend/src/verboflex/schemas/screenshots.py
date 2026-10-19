"""Authenticated code context and on-demand screenshot contracts."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from verboflex.localization.code_keys.catalog import CodeOccurrence, CodePreview


class ScreenshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_function: Annotated[str, Field(min_length=1, max_length=512)]
    theme: Literal["light", "dark"] = "light"
    proposal_version: Annotated[int, Field(ge=1)] | None = None


class ScreenshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    state: Literal["queued", "rendering", "succeeded", "failed", "cancelled", "expired"]
    request: ScreenshotRequest
    input_digest: str
    image_digest: str | None
    error_code: str | None
    created_at: datetime
    expires_at: datetime


class ScreenshotPage(BaseModel):
    items: list[ScreenshotResponse]
    next_cursor: UUID | None


class CodeContextResponse(BaseModel):
    configured: bool
    occurrences: list[CodeOccurrence]
    previews: list[CodePreview]
    capture_functions: list[str]
    code_commit: str | None = None
    occurrences_truncated: bool = False


class CodeCatalogEntry(BaseModel):
    key: str
    missing_translation: bool
    missing_base: bool


class CodeCatalogPage(BaseModel):
    items: list[CodeCatalogEntry]
    next_cursor: str | None
    orphan_count: int


class CodeSourceSummary(BaseModel):
    scope_id: UUID
    mapping_id: UUID
    key_count: int
    missing_count: int


class CodeSourcePage(BaseModel):
    items: list[CodeSourceSummary]
    next_cursor: UUID | None
