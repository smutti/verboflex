"""Closed administrator contracts for internal-user administration."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from verboflex.schemas.users import RoleName


class AdminUserCreateRequest(BaseModel):
    """Create one immutable corporate-email identity with additive roles."""

    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(min_length=1, max_length=320)]
    display_name: Annotated[str, Field(min_length=1, max_length=200)]
    roles: Annotated[list[RoleName], Field(min_length=1, max_length=4)]

    @field_validator("roles")
    @classmethod
    def collapse_duplicate_roles(cls, roles: list[RoleName]) -> list[RoleName]:
        """Treat submitted role names as a set while preserving fixed enum order."""
        selected = frozenset(roles)
        return [role for role in RoleName if role in selected]


class AdminUserUpdateRequest(BaseModel):
    """The only ordinary fields an administrator may change."""

    model_config = ConfigDict(extra="forbid")

    display_name: Annotated[str, Field(min_length=1, max_length=200)]
    roles: Annotated[list[RoleName], Field(min_length=1, max_length=4)]

    @field_validator("roles")
    @classmethod
    def collapse_duplicate_roles(cls, roles: list[RoleName]) -> list[RoleName]:
        """Treat duplicate authority names as one fixed-order set member."""
        selected = frozenset(roles)
        return [role for role in RoleName if role in selected]


class AdminUserResponse(BaseModel):
    """Ordinary internal-user projection with no credential material."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: str
    display_name: str
    roles: list[RoleName]
    is_active: bool
    must_change_password: bool


class AdminUserCredentialResponse(AdminUserResponse):
    """One successful lifecycle response that reveals a temporary password once."""

    temporary_password: str = Field(repr=False, min_length=12, max_length=128)


class AdminUserListResponse(BaseModel):
    """Stable keyset page of internal users."""

    model_config = ConfigDict(extra="forbid")

    items: list[AdminUserResponse]
    next_cursor: str | None
