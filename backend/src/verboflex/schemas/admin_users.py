"""Closed administrator contracts for internal-user administration."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from verboflex.schemas.product_team import ProductRole
from verboflex.schemas.users import RoleName


def _ordered_unique_roles(roles: list[RoleName]) -> list[RoleName]:
    selected = frozenset(roles)
    return [role for role in RoleName if role in selected]


class AdminUserProductAssignment(BaseModel):
    """One initial product membership for a newly created account."""

    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    role: ProductRole


class AdminUserCreateRequest(BaseModel):
    """Create one identity with global roles and optional product memberships."""

    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(min_length=1, max_length=320)]
    display_name: Annotated[str, Field(min_length=1, max_length=200)]
    roles: Annotated[list[RoleName], Field(min_length=1, max_length=4)]
    product_assignments: list[AdminUserProductAssignment] = Field(
        default_factory=list, max_length=100
    )

    @field_validator("product_assignments")
    @classmethod
    def unique_products(
        cls, assignments: list[AdminUserProductAssignment]
    ) -> list[AdminUserProductAssignment]:
        if len({assignment.product_id for assignment in assignments}) != len(assignments):
            raise ValueError("Select each product only once")
        return assignments

    @field_validator("roles")
    @classmethod
    def collapse_duplicate_roles(cls, roles: list[RoleName]) -> list[RoleName]:
        """Treat submitted role names as a set while preserving fixed enum order."""
        return _ordered_unique_roles(roles)


class AdminUserUpdateRequest(BaseModel):
    """The only ordinary fields an administrator may change."""

    model_config = ConfigDict(extra="forbid")

    display_name: Annotated[str, Field(min_length=1, max_length=200)]
    roles: Annotated[list[RoleName], Field(min_length=1, max_length=4)]

    @field_validator("roles")
    @classmethod
    def collapse_duplicate_roles(cls, roles: list[RoleName]) -> list[RoleName]:
        """Treat duplicate authority names as one fixed-order set member."""
        return _ordered_unique_roles(roles)


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
