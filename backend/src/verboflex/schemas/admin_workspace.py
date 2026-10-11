"""Workspace configuration and live repository picker contracts."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from verboflex.services.repositories import normalize_repository_identity


class AdminWorkspaceResponse(BaseModel):
    workspace: str | None


class AdminWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace: str = Field(min_length=1, max_length=100)

    @field_validator("workspace")
    @classmethod
    def normalize_workspace(cls, value: str) -> str:
        return normalize_repository_identity(value, "repository")[0]


class AdminBitbucketRepositoryResponse(BaseModel):
    workspace: str
    repository_slug: str
    name: str


class AdminBitbucketRepositoryListResponse(BaseModel):
    workspace: str
    items: list[AdminBitbucketRepositoryResponse]
    next_cursor: str | None
