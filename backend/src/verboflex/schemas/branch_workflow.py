"""Approval branch workflow HTTP contract."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from verboflex.schemas.submissions import ClosedModel


class ConfigureBranchWorkflow(ClosedModel):
    mapping_id: UUID
    work_branch: Annotated[str, Field(min_length=1, max_length=255)]
    target_branch: Annotated[str, Field(min_length=1, max_length=255)]


class BranchChange(ClosedModel):
    id: UUID
    sequence: int
    kind: Literal["commit", "pull_request", "html_language", "language"]
    state: Literal[
        "queued", "running", "sending", "committed", "open", "merged", "declined", "blocked"
    ]
    label: str
    created_at: datetime
    commit_hash: str | None
    commit_url: str | None
    pr_url: str | None
    error_code: str | None
    can_retry: bool
    catalog_refresh_state: (
        Literal["pending", "running", "succeeded", "failed", "skipped"] | None
    ) = None


class BranchWorkflowChoice(ClosedModel):
    id: UUID
    repository: str
    work_branch: str
    target_branch: str
    active: bool


class BranchMappingChoice(ClosedModel):
    mapping_id: UUID
    repository: str
    source_branch: str
    workflow_id: UUID | None


class BranchWorkflowResponse(ClosedModel):
    enabled: bool
    workflow_id: UUID | None = None
    workflows: list[BranchWorkflowChoice] = []
    available_mappings: list[BranchMappingChoice] = []
    repository: str | None = None
    work_branch: str | None = None
    target_branch: str | None = None
    can_publish: bool = False
    can_add_html_language: bool = False
    can_add_language: bool = False
    pr_reviewer_name: str | None = None
    can_create_pr: bool = False
    open_pr_url: str | None = None
    publication_retry_at: datetime | None = None
    waiting_changes: int = 0
    creating_pr: bool = False
    blocked_change: BranchChange | None = None
    items: list[BranchChange] = []
    next_before: int | None = None
