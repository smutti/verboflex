"""Provider-independent user contracts."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleName(StrEnum):
    """Stable role identifiers exposed by the API."""

    ADMIN = "admin"
    PRODUCT_MANAGER_REVIEWER = "product_manager_reviewer"
    TRANSLATOR = "translator"
    VIEWER = "viewer"


class CurrentUserResponse(BaseModel):
    """Authenticated caller identity without persistence details."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: EmailStr
    display_name: str
    roles: list[RoleName]
    must_change_password: bool
    product_roles: dict[UUID, list[RoleName]] = Field(default_factory=dict)
    managed_product_ids: list[UUID] = Field(default_factory=list)


class MentionUserResponse(BaseModel):
    """Minimal active-user identity exposed to the mention selector."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    display_name: str
    email: EmailStr
