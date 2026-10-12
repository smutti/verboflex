"""Closed product-team contracts; only provisioning returns a temporary password."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ProductRole = Literal["viewer", "translator", "product_manager_reviewer", "product_owner"]
CollaboratorRole = Literal["viewer", "translator", "product_manager_reviewer"]


class TeamModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductAccess(TeamModel):
    role: str | None
    roles: list[str]
    can_manage_team: bool


class MemberInput(TeamModel):
    email: str = Field(min_length=1, max_length=320)
    role: ProductRole
    expected_version: UUID | None = None


class AddMemberInput(TeamModel):
    email: str = Field(min_length=1, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    role: CollaboratorRole


class MemberAdded(TeamModel):
    user_id: UUID
    email: str
    account_created: bool
    temporary_password: str | None = Field(default=None, repr=False, min_length=12, max_length=128)


class TeamMember(TeamModel):
    user_id: UUID
    email: str
    display_name: str
    role: ProductRole
    version: UUID
    account_active: bool


class TeamResponse(TeamModel):
    access: ProductAccess
    members: list[TeamMember]
    has_active_owner: bool
