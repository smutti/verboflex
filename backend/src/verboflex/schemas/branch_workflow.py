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
    kind: Literal["commit", "pull_request"]
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
    can_create_pr: bool = False
    items: list[BranchChange] = []
    next_before: int | None = None
