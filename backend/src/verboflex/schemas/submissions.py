"""Closed, generated public review projections; never expose prepared source bytes."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from verboflex.localization.writing.core import WritebackReason

Version = Annotated[StrictInt, Field(ge=1, le=9_007_199_254_740_991)]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SelectedProposal(ClosedModel):
    proposal_id: UUID
    expected_version: Version


class MappingTarget(ClosedModel):
    mapping_id: UUID
    target_branch: Annotated[str, Field(min_length=1, max_length=255)]


class CreateSubmissionReviewRequest(ClosedModel):
    proposals: Annotated[list[SelectedProposal], Field(min_length=1, max_length=100)]
    targets: Annotated[list[MappingTarget], Field(max_length=100)] = []

    @model_validator(mode="after")
    def unique_identities(self) -> CreateSubmissionReviewRequest:
        if len({p.proposal_id for p in self.proposals}) != len(self.proposals):
            raise ValueError("duplicate proposal selection")
        if len({t.mapping_id for t in self.targets}) != len(self.targets):
            raise ValueError("duplicate mapping target")
        return self


class MappingDestination(ClosedModel):
    mapping_id: UUID
    repository_id: UUID
    workspace: str
    repository_slug: str
    allowed_targets: list[str]
    default_target: str
    chosen_target: str


class ChangeSetCandidate(ClosedModel):
    proposal_id: UUID
    version: int
    key: str
    language: str
    state: Literal["draft", "approved", "rejected"]
    value_count: int
    can_review: bool
    blocker: WritebackReason | None
    mapping_id: UUID | None = None
    published_excerpt: str = ""
    proposed_excerpt: str = ""


class ChangeSetCandidatesResponse(ClosedModel):
    product_id: UUID
    active_revision_id: UUID
    can_request_review: bool
    max_selected_proposals: int = 100
    max_submission_groups: int = 20
    max_files: int = 500
    max_values: int = 5000
    max_file_bytes: int = 1_048_576
    max_batch_bytes: int = 20_971_520
    destinations: list[MappingDestination] = []
    items: list[ChangeSetCandidate]
    next_after: UUID | None = None


class ReviewedValue(ClosedModel):
    proposal_id: UUID
    value_id: UUID
    language: str
    selector_kind: str
    published_text: str
    proposed_text: str
    selector: str = ""
    effective_maximum: int | None = None
    character_count: int = 0
    group_id: UUID | None = None
    proposal_version: int = 0
    key: str = ""
    file_path: str = ""


class ReviewedSource(ClosedModel):
    mapping_id: UUID
    repository_side: str
    repository_id: UUID
    branch: str
    commit_hash: str


class ReviewedGroup(ClosedModel):
    id: UUID
    repository_id: UUID
    workspace: str
    repository_slug: str
    target_branch: str
    target_head: str
    source_branch: str
    proposal_ids: list[UUID]
    value_count: int
    file_count: int
    sources: list[ReviewedSource]


class ReviewedFile(ClosedModel):
    index: int
    group_id: UUID
    path: str
    before_sha256: str
    after_sha256: str
    changed_values: int


class ReviewFilesPage(ClosedModel):
    items: list[ReviewedFile]
    next_after: int | None


class ReviewValuesPage(ClosedModel):
    items: list[ReviewedValue]
    next_after: int | None


class SubmissionReviewResponse(ClosedModel):
    id: UUID
    product_id: UUID
    active_revision_id: UUID
    state: Literal["queued", "running", "ready", "failed", "expired", "accepted"]
    attempt: int
    created_at: datetime
    started_at: datetime | None
    expires_at: datetime
    error_code: WritebackReason | None
    values: list[ReviewedValue]
    file_count: int = 0
    manifest_digest: str | None = None
    proposal_count: int = 0
    value_count: int = 0
    groups: list[ReviewedGroup] = []
    destinations: list[MappingDestination] = []
    next_values_after: int | None = None
    batch_id: UUID | None = None


class SubmissionReviewError(ClosedModel):
    detail: str
    code: str


Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
CommitHash = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
BranchName = Annotated[str, Field(min_length=1, max_length=255)]
ChangeSetStatus = Literal[
    "queued",
    "running",
    "reconciling",
    "blocked",
    "failed",
    "succeeded",
    "needs_attention",
    "resolved",
]
ChangeSetStage = Literal["branch", "commit", "pull_request", "complete"]


class CreateSubmissionBatchRequest(ClosedModel):
    review_id: UUID
    expected_review_attempt: Version
    expected_content_digest: Digest
    request_key: UUID


class SubmissionActionRequest(ClosedModel):
    expected_attempt: Version


class ChangeSetSource(ClosedModel):
    mapping_id: UUID
    repository_id: UUID
    repository_side: Literal["direct", "keys", "translations"]
    workspace: Annotated[str, Field(min_length=1, max_length=100)]
    repository_slug: Annotated[str, Field(min_length=1, max_length=100)]
    branch: BranchName
    commit_hash: CommitHash
    import_execution_id: UUID


class ChangeSetItemResponse(ClosedModel):
    proposal_id: UUID
    proposal_version: int
    key_id: UUID
    key: str
    key_truncated: bool = False
    language: str
    value_count: int
    current_version: int | None
    newer_version_available: bool


class ChangeSetValueResponse(ClosedModel):
    proposal_id: UUID
    proposal_version: int
    value_id: UUID
    key: str
    language: str
    selector_kind: str
    selector: str
    published_text: str
    proposed_text: str
    file_path: str
    basis_revision_number: int
    basis_digest: str
    source: ChangeSetSource | None


class ChangeSetFileResponse(ClosedModel):
    id: UUID
    path: str
    before_sha256: str
    after_sha256: str
    before_bytes: int
    after_bytes: int
    attributes: list[Literal["binary"]]
    changed_values: int
    source: ChangeSetSource | None
    format: Literal["android_xml", "qt_ts", "json", "ios_strings"] | None


class BranchReceiptResponse(ClosedModel):
    kind: Literal["branch"] = "branch"
    name: BranchName
    commit_hash: CommitHash


class CommitReceiptResponse(ClosedModel):
    kind: Literal["commit"] = "commit"
    commit_hash: CommitHash
    parent: CommitHash
    branch: BranchName
    manifest_digest: Digest


class PullRequestReceiptResponse(ClosedModel):
    kind: Literal["pull_request"] = "pull_request"
    id: Version
    url: str | None
    state: Literal["OPEN", "MERGED", "DECLINED", "SUPERSEDED"]
    source_branch: BranchName
    source_commit: CommitHash
    target_branch: BranchName
    target_commit: CommitHash


class AuthorityReceiptResponse(ClosedModel):
    kind: Literal["authority"] = "authority"
    action: Literal[
        "retry",
        "reconcile",
        "resume_explicit_retry",
        "reconciliation_started",
        "reauthorized",
        "needs_review_resolved",
        "pull_request_terminal",
        "admin_receipt_adoption",
    ]
    actor_id: UUID | None = None
    pull_request_id: int | None = None


class ChangeSetActivityResponse(ClosedModel):
    id: UUID
    event_kind: Literal[
        "send_intent", "observation", "reauthorization", "finalization", "pr_status"
    ]
    step: Literal["branch", "commit", "pull_request", "authority"]
    outcome: Literal["intent", "verified", "not_sent", "unknown", "conflict"]
    attempt: int
    created_at: datetime
    receipt: (
        Annotated[
            BranchReceiptResponse
            | CommitReceiptResponse
            | PullRequestReceiptResponse
            | AuthorityReceiptResponse,
            Field(discriminator="kind"),
        ]
        | None
    )


class SubmissionActor(ClosedModel):
    id: UUID
    display_name: Annotated[str, Field(max_length=200)]


class PullRequestTracking(ClosedModel):
    source_commit: str
    target_commit: str
    merge_status: Literal["clean", "conflicts", "unknown", "not_applicable"]
    content_status: Literal["original", "verified", "changed", "unverified"]
    checked_at: datetime


class ChangeSetResponse(ClosedModel):
    id: UUID
    batch_id: UUID
    status: ChangeSetStatus
    stage: ChangeSetStage
    attempt: int
    repository_id: UUID
    workspace: str
    repository_slug: str
    target_branch: str
    target_head: str
    source_branch: str
    proposal_count: int
    value_count: int
    file_count: int
    error_code: str | None
    can_retry: bool = False
    can_reconcile: bool = False
    can_finalize: bool = False
    recovery_reason: (
        Literal[
            "resolved",
            "in_progress",
            "reconciliation_required",
            "original_actor_required",
            "fresh_authority_required",
        ]
        | None
    ) = None
    pr_id: int | None
    pr_url: str | None
    pr_state: str | None
    pr_tracking: PullRequestTracking | None = None
    created_at: datetime

    attempt_started_at: datetime | None = None
    finished_at: datetime | None = None
    branch_commit: str | None = None
    commit_hash: str | None = None
    sources: list[ChangeSetSource] = []
    provenance_available: bool = False
    actor: SubmissionActor | None = None


class SubmissionBatchResponse(ClosedModel):
    id: UUID
    product_id: UUID
    review_id: UUID
    request_key: UUID
    created_at: datetime
    groups: list[ChangeSetResponse]


class ChangeSetHistoryPage(ClosedModel):
    items: list[ChangeSetResponse]
    next_cursor: str | None
    page_size: int = 25


class ChangeSetItemsPage(ClosedModel):
    items: list[ChangeSetItemResponse]
    next_cursor: str | None
    page_size: int = 25


class ChangeSetValuesPage(ClosedModel):
    items: list[ChangeSetValueResponse]
    next_cursor: str | None
    page_size: int = 25


class ChangeSetFilesPage(ClosedModel):
    items: list[ChangeSetFileResponse]
    next_cursor: str | None
    page_size: int = 25


class ChangeSetActivityPage(ClosedModel):
    items: list[ChangeSetActivityResponse]
    next_cursor: str | None
    page_size: int = 25
