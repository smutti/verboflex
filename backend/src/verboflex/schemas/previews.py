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


class AdminPreviewLayoutCandidateResponse(BaseModel):
    """Closed empty pre-detector candidate shape expanded by the detector plans."""

    model_config = ConfigDict(extra="forbid")


class AdminPreviewJobResultResponse(BaseModel):
    """Exact noncanonical skeleton result with no provider or source payload."""

    model_config = ConfigDict(extra="forbid")

    detector_version: Annotated[str, Field(min_length=1, max_length=64)]
    digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    layout_candidates: Annotated[
        list[AdminPreviewLayoutCandidateResponse],
        Field(max_length=0),
    ]


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
    result: AdminPreviewJobResultResponse | None
    error_code: (
        Literal[
            "enqueue_failed",
            "processing_failed",
            "stale_attempt",
            "stale_candidate",
            "stale_connection",
            "stale_identity",
            "time_limit_exceeded",
        ]
        | None
    )
    is_current: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
