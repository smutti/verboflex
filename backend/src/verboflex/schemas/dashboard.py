"""Closed, metadata-only personal dashboard projections."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from verboflex.schemas.submissions import ChangeSetStatus


class DashboardProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str


class DashboardActor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    display_name: str


class DashboardReviewEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    kind: Literal["proposal_saved", "state_changed"]
    occurred_at: datetime
    product: DashboardProduct
    actor: DashboardActor
    translation_group_id: UUID
    language: str
    key_excerpt: str = Field(max_length=160)
    from_state: Literal["draft", "approved", "rejected"] | None
    to_state: Literal["draft", "approved", "rejected"] | None


class DashboardCommentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    kind: Literal["comment_created", "comment_edited", "comment_removed"]
    occurred_at: datetime
    product: DashboardProduct
    actor: DashboardActor
    translation_group_id: UUID
    language: str
    key_excerpt: str = Field(max_length=160)
    comment_id: UUID | None
    comment_status: Literal["available", "removed"]


class DashboardSubmissionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    kind: Literal["change_set_submitted"]
    occurred_at: datetime
    product: DashboardProduct
    actor: DashboardActor
    change_set_id: UUID
    current_status: ChangeSetStatus


class DashboardImportEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    kind: Literal["current_import_completed"]
    occurred_at: datetime
    product: DashboardProduct
    actor: None


DashboardEvent = Annotated[
    DashboardReviewEvent | DashboardCommentEvent | DashboardSubmissionEvent | DashboardImportEvent,
    Field(discriminator="kind"),
]


class DashboardFeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DashboardEvent] = Field(max_length=3)
    has_more: bool


class DashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    my_activity: DashboardFeed
    project_updates: DashboardFeed


class ProjectUpdatesPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DashboardEvent] = Field(max_length=20)
    next_cursor: str | None
