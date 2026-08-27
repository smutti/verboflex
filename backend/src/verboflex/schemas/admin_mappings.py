"""Closed administrator contracts for candidate-owned repository mappings."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminDirectMappingWriteRequest(BaseModel):
    """Create or replace one direct mapping under candidate-version authority."""

    model_config = ConfigDict(extra="forbid")

    topology: Literal["direct"]
    repository_id: UUID
    source_branch: Annotated[str, Field(min_length=1, max_length=255)]
    allowed_target_branches: Annotated[list[str], Field(min_length=1, max_length=100)]
    default_target_branch: Annotated[str, Field(min_length=1, max_length=255)]
    expected_candidate_version: Annotated[int, Field(ge=1)]


class AdminMappingResponse(BaseModel):
    """One lifecycle-free direct or separate mapping projection."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    topology: Literal["direct", "separate"]
    primary_repository_id: UUID
    primary_source_branch: str
    translations_repository_id: UUID | None
    translations_source_branch: str | None
    allowed_target_branches: list[str]
    default_target_branch: str
    selected_layout_candidate_id: UUID | None
    selected_layout_version: int | None
    candidate_version: int


class AdminMappingListResponse(BaseModel):
    """One bounded exact-order candidate mapping page."""

    model_config = ConfigDict(extra="forbid")

    items: list[AdminMappingResponse]
    next_cursor: str | None


class AdminMappingConflictResponse(BaseModel):
    """Form-addressable candidate mapping conflict."""

    model_config = ConfigDict(extra="forbid")

    detail: str
    field: Literal[
        "mapping_identity",
        "candidate_version",
        "source_branch",
        "allowed_target_branches",
    ]
