"""Bounded bulk approval preview and durable operation status."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from verboflex.schemas.authoring import ClosedModel


class AuthoringApprovalInput(ClosedModel):
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class AuthoringApprovalStatus(ClosedModel):
    id: UUID
    state: Literal["queued", "succeeded", "failed"]
    count: int
    error: str | None
    branch_job_ids: list[UUID]
    created_at: datetime


class AuthoringApprovalPreview(ClosedModel):
    count: int
    languages: dict[str, int]
    source_changed: int
    over_limit: bool
    fingerprint: str
    latest: AuthoringApprovalStatus | None
