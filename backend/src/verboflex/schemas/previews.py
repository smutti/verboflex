"""Closed administrator preview-job request and status contracts."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminPreviewCommitRequest(BaseModel):
    """One resolved commit associated with a server-owned mapping role."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["direct", "keys", "translations"]
    commit_hash: Annotated[str, Field(pattern=r"^[0-9A-Fa-f]{40}$")]


class AdminPreviewJobCreateRequest(BaseModel):
    """Candidate compare value plus exact resolved commits, with no source bytes."""

    model_config = ConfigDict(extra="forbid")

    expected_candidate_version: Annotated[int, Field(ge=1)]
    commits: Annotated[list[AdminPreviewCommitRequest], Field(min_length=1, max_length=2)]


class AdminPreviewRepositorySideResponse(BaseModel):
    """One credential-free commit-bound repository side."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["direct", "keys", "translations"]
    repository_id: UUID
    source_branch: str
    commit_hash: str


class AdminPreviewJobResponse(BaseModel):
    """Bounded PostgreSQL-authoritative attempt state and deterministic result."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    input_digest: str
    attempt: int
    state: Literal["queued", "running", "succeeded", "failed", "timed_out"]
    product_id: UUID
    candidate_revision_id: UUID
    candidate_revision_version: int
    mapping_id: UUID
    connection_generation: int
    detector_version: str
    repository_sides: list[AdminPreviewRepositorySideResponse]
    result: dict[str, object] | None
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
