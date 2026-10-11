"""Closed browser contracts for live repository discovery."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class AdminBranchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    commit_hash: str


class AdminBranchListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AdminBranchResponse]
    next_cursor: str | None


class AdminSourceFileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    size: int


class AdminSourceDiscoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commit_hash: str
    files: list[AdminSourceFileResponse]
    total_bytes: int


class AdminDiscoveryErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: Literal["Repository discovery unavailable"]
    state: Literal[
        "disconnected",
        "reauthorization_required",
        "permission_denied",
        "not_found",
        "rate_limited",
        "unavailable",
        "timeout",
        "invalid_source",
        "limit_exceeded",
    ]
