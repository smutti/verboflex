"""Closed administrator contracts for versioned product configuration."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminProductCreateRequest(BaseModel):
    """Create one stable product identity and its initial candidate revision."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=1000)]
    description: str | None = None


class AdminProductUpdateRequest(BaseModel):
    """Compare and save the current candidate configuration."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=1000)]
    description: str | None = None
    expected_candidate_version: Annotated[int, Field(ge=1)]


class AdminProductRevisionSummary(BaseModel):
    """Bounded active or candidate revision projection."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    version: int
    description: str | None
    is_published: bool


class AdminProductResponse(BaseModel):
    """Stable product identity with explicitly separate revision states."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    is_active: bool
    active_revision: AdminProductRevisionSummary | None
    candidate_revision: AdminProductRevisionSummary | None


class AdminProductListResponse(BaseModel):
    """One bounded stable keyset page of products."""

    model_config = ConfigDict(extra="forbid")

    items: list[AdminProductResponse]
    next_cursor: str | None


class AdminProductConflictResponse(BaseModel):
    """Bounded conflict with optional field affinity for form recovery."""

    model_config = ConfigDict(extra="forbid")

    detail: str
    field: Literal["name"] | None = None


AdminProductStatus = Literal["active", "inactive"]
