"""Closed administrator contracts for the reusable repository registry."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminRepositoryCreateRequest(BaseModel):
    """Register one provider identity without credentials or product settings."""

    model_config = ConfigDict(extra="forbid")

    workspace: Annotated[str, Field(min_length=1, max_length=100)]
    repository_slug: Annotated[str, Field(min_length=1, max_length=100)]
    descriptive_name: Annotated[str, Field(max_length=120)] | None = None


class AdminRepositoryResponse(BaseModel):
    """Credential-free reusable repository selection projection."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    workspace: str
    repository_slug: str
    descriptive_name: str | None
    provider: Literal["bitbucket", "github"] = "bitbucket"


class AdminRepositoryListResponse(BaseModel):
    """One bounded stable keyset page of repository identities."""

    model_config = ConfigDict(extra="forbid")

    items: list[AdminRepositoryResponse]
    next_cursor: str | None
