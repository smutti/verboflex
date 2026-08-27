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


class AdminDiscoveryErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: Literal["Bitbucket discovery unavailable"]
    state: Literal[
        "disconnected",
        "reauthorization_required",
        "permission_denied",
        "not_found",
        "unavailable",
        "timeout",
    ]
