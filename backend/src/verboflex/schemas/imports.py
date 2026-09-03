"""Closed administrator contracts for published-mapping imports."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminImportRepositorySideResponse(BaseModel):
    """One credential-free configured repository selector."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["direct", "keys", "translations"]
    repository_id: UUID
    source_branch: Annotated[str, Field(min_length=1, max_length=255)]


class AdminImportSourceReferenceResponse(BaseModel):
    """One exact metadata-only file reference from an immutable commit."""

    model_config = ConfigDict(extra="forbid")

    position: Annotated[int, Field(ge=0)]
    repository_side: Literal["direct", "keys", "translations"]
    repository_id: UUID
    source_branch: Annotated[str, Field(min_length=1, max_length=255)]
    commit_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    path: Annotated[str, Field(min_length=1, max_length=4096)]
    size_bytes: Annotated[int, Field(ge=0, le=1_048_576)]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class AdminImportBaselineResponse(BaseModel):
    """The last successful baseline retained independently from current work."""

    model_config = ConfigDict(extra="forbid")

    imported_at: datetime
    source_references: Annotated[
        list[AdminImportSourceReferenceResponse],
        Field(max_length=500),
    ]


class AdminPublishedMappingImportResponse(BaseModel):
    """One server-owned published mapping and its current logical import state."""

    model_config = ConfigDict(extra="forbid")

    id: UUID | None
    mapping_id: UUID
    active_revision_id: UUID
    topology: Literal["direct", "separate"]
    repository_sides: Annotated[
        list[AdminImportRepositorySideResponse],
        Field(min_length=1, max_length=2),
    ]
    state: Literal[
        "not_imported",
        "queued",
        "running",
        "current",
        "import_failed",
    ]
    active_baseline: AdminImportBaselineResponse | None
    latest_execution_at: datetime | None
    retry_count: Annotated[int, Field(ge=0)]
    error_category: Literal["provider_unavailable"] | None
    error_message: Annotated[str, Field(min_length=1, max_length=256)] | None


class AdminPublishedMappingImportListResponse(BaseModel):
    """Bounded server-ordered published mapping import collection."""

    model_config = ConfigDict(extra="forbid")

    items: Annotated[list[AdminPublishedMappingImportResponse], Field(max_length=100)]
    next_cursor: None = None


class AdminImportRewriteSideResponse(BaseModel):
    """Exact old/new commits and bounded change counts for one mapping side."""

    model_config = ConfigDict(extra="forbid")

    repository_side: Literal["direct", "keys", "translations"]
    repository_id: UUID
    old_commit_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    new_commit_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    added_count: Annotated[int, Field(ge=0, le=500)]
    modified_count: Annotated[int, Field(ge=0, le=500)]
    removed_count: Annotated[int, Field(ge=0, le=500)]


class AdminImportRewriteDeltaResponse(BaseModel):
    """One ordered localization-file metadata row without provider content."""

    model_config = ConfigDict(extra="forbid")

    position: Annotated[int, Field(ge=0, le=499)]
    repository_side: Literal["direct", "keys", "translations"]
    change: Literal["added", "modified", "removed"]
    path: Annotated[str, Field(min_length=1, max_length=4096)]


class AdminImportRewriteComparisonResponse(BaseModel):
    """Complete current proposal authority for one mapping-level decision."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID
    import_id: UUID
    mapping_id: UUID
    proposed_execution_id: UUID
    proposal_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    topology: Literal["direct", "separate"]
    confirmable: Literal[True]
    sides: Annotated[list[AdminImportRewriteSideResponse], Field(min_length=1, max_length=2)]
    files: Annotated[list[AdminImportRewriteDeltaResponse], Field(max_length=500)]


class AdminImportRewriteConfirmationRequest(BaseModel):
    """Expected immutable proposal identity supplied by an untrusted browser."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID
    proposed_execution_id: UUID
    proposal_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
