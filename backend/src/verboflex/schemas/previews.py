"""Closed administrator preview-job request and status contracts."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from verboflex.schemas.duplicate_reports import DuplicateReportSummaryResponse

AdminActiveRevisionRevalidationErrorCode = (
    Literal[
        "enqueue_failed",
        "processing_failed",
        "stale_attempt",
        "stale_active_revision",
        "stale_connection",
        "stale_identity",
        "time_limit_exceeded",
    ]
    | None
)


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


class AdminPreviewConfirmationRequest(BaseModel):
    """Exact compare values for one explicit current layout assignment."""

    model_config = ConfigDict(extra="forbid")

    preview_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    layout_candidate_id: UUID
    layout_candidate_version: Literal[1]
    base_language: Annotated[str, Field(min_length=1, max_length=64)] | None


class AdminPreviewConfirmationResponse(BaseModel):
    """Bounded actor/time evidence for one confirmed preview layout."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    mapping_id: UUID
    preview_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    layout_candidate_id: UUID
    layout_candidate_version: Literal[1]
    base_language: Annotated[str, Field(min_length=1, max_length=64)]
    confirmed_by: UUID
    confirmed_at: datetime


class AdminPreviewRepositorySideResponse(BaseModel):
    """One credential-free commit-bound repository side."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["direct", "keys", "translations"]
    repository_id: UUID
    source_branch: str
    commit_hash: str


class AdminPreviewSampleResponse(BaseModel):
    """One bounded read-only sample, not a canonical translation."""

    model_config = ConfigDict(extra="forbid")

    language: Annotated[str, Field(min_length=1, max_length=64)]
    key: Annotated[str, Field(min_length=1, max_length=1_048_576)]
    translation: Annotated[str, Field(max_length=1_048_576)]


class AdminPreviewLayoutCandidateResponse(BaseModel):
    """One bounded noncanonical exact-layout preview candidate."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    version: Literal[1]
    repository_side: Literal["direct", "keys", "translations"]
    format: Literal["android_xml", "qt_ts", "json", "ios_strings"]
    layout_identity: Annotated[str, Field(min_length=1, max_length=4096)]
    confidence: Annotated[float, Field(ge=1.0, le=1.0)]
    files: Annotated[list[str], Field(min_length=1, max_length=500)]
    languages: Annotated[list[str], Field(min_length=1, max_length=32)]
    keys: Annotated[list[str], Field(min_length=1, max_length=100)]
    samples: Annotated[list[AdminPreviewSampleResponse], Field(min_length=1, max_length=100)]
    samples_are_partial: Literal[True]


class AdminPreviewJobResultResponse(BaseModel):
    """Exact noncanonical preview result with no provider or source payload."""

    model_config = ConfigDict(extra="forbid")

    detector_version: Annotated[str, Field(min_length=1, max_length=64)]
    digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    layout_candidates: Annotated[
        list[AdminPreviewLayoutCandidateResponse],
        Field(max_length=500),
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
    diagnostic_code: Literal["repository_scan_limit_reached"] | None
    duplicate_report_summary: DuplicateReportSummaryResponse | None = None
    is_current: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AdminActiveRevisionRevalidationJobCreateRequest(BaseModel):
    """Exact published-revision compare values with commit-only provider identity."""

    model_config = ConfigDict(extra="forbid")

    expected_active_revision_version: Annotated[int, Field(ge=1)]
    commits: Annotated[list[AdminPreviewCommitRequest], Field(min_length=1, max_length=2)]


class AdminActiveRevisionRevalidationConfirmationRequest(BaseModel):
    """Complete caller compare identity for one active-revision confirmation."""

    model_config = ConfigDict(extra="forbid")

    active_revision_id: UUID
    active_revision_version: Annotated[int, Field(ge=1)]
    mapping_id: UUID
    connection_generation: Annotated[int, Field(ge=0)]
    commits: Annotated[list[AdminPreviewCommitRequest], Field(min_length=1, max_length=2)]
    preview_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    layout_candidate_id: UUID
    layout_candidate_version: Literal[1]
    base_language: Annotated[str, Field(min_length=1, max_length=64)] | None


class AdminActiveRevisionRevalidationJobResponse(BaseModel):
    """Bounded active-revision job projection with no candidate terminology."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    input_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    attempt: Annotated[int, Field(ge=1)]
    state: Literal["queued", "running", "succeeded", "failed", "timed_out"]
    product_id: UUID
    active_revision_id: UUID
    active_revision_version: Annotated[int, Field(ge=1)]
    mapping_id: UUID
    connection_generation: Annotated[int, Field(ge=0)]
    detector_version: Annotated[str, Field(min_length=1, max_length=64)]
    repository_sides: Annotated[
        list[AdminPreviewRepositorySideResponse],
        Field(min_length=1, max_length=2),
    ]
    result: AdminPreviewJobResultResponse | None
    error_code: AdminActiveRevisionRevalidationErrorCode
    diagnostic_code: Literal["repository_scan_limit_reached"] | None
    duplicate_report_summary: DuplicateReportSummaryResponse | None = None
    is_current: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AdminActiveRevisionRevalidationConfirmationResponse(BaseModel):
    """Immutable bounded evidence for one exact published-revision job."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    product_id: UUID
    active_revision_id: UUID
    active_revision_version: Annotated[int, Field(ge=1)]
    mapping_id: UUID
    connection_generation: Annotated[int, Field(ge=0)]
    commits: Annotated[
        list[AdminPreviewRepositorySideResponse],
        Field(min_length=1, max_length=2),
    ]
    preview_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    layout_candidate_id: UUID
    layout_candidate_version: Literal[1]
    base_language: Annotated[str, Field(min_length=1, max_length=64)]
    confirmed_by: UUID
    confirmed_at: datetime
