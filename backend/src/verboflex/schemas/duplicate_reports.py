"""Read-only bounded diagnostic projections."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DuplicateSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository_side: str
    repository_id: str
    source_branch: str
    commit_hash: str


class DuplicateOccurrenceResponse(BaseModel):
    path: str
    resource_position: int


class DuplicateReportSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    complete: bool
    group_count: Annotated[int, Field(ge=0, le=50_000)]
    repeated_occurrences: Annotated[int, Field(ge=0, le=50_000)]


class DuplicateGroupResponse(BaseModel):
    id: str
    repository_side: str
    language: str
    key_preview: str
    key_length: int
    occurrence_count: int
    occurrences: list[DuplicateOccurrenceResponse]
    next_occurrence_cursor: str | None


class DuplicateReportResponse(BaseModel):
    report_id: UUID
    execution: int
    complete: bool
    issue_codes: list[str]
    group_count: int
    repeated_occurrences: int
    sources: list[DuplicateSourceResponse]
    items: list[DuplicateGroupResponse]
    next_cursor: str | None
