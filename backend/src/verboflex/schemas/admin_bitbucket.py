"""Closed administrator contracts for the organizational Bitbucket connection."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

AdminBitbucketCapabilityReadiness = Literal[
    "disconnected",
    "ready",
    "ready_for_later_phase",
    "reauthorization_required",
    "unavailable",
]


class AdminBitbucketCapabilityProfile(BaseModel):
    """Closed readiness evidence without provider authority or generation detail."""

    model_config = ConfigDict(extra="forbid")

    source_read: AdminBitbucketCapabilityReadiness
    source_write: AdminBitbucketCapabilityReadiness
    pull_request: AdminBitbucketCapabilityReadiness
    evaluated_at: datetime | None


class AdminBitbucketStatusResponse(BaseModel):
    """Bounded connection state safe for browser projection."""

    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "Disconnected",
        "Connected",
        "Reauthorization required",
        "Unavailable",
    ]
    scope_profile: Literal["repository_and_pull_request"] = "repository_and_pull_request"
    scope_label: Literal[
        "Repository and pull-request access"
    ] = "Repository and pull-request access"
    capability_profile: AdminBitbucketCapabilityProfile
    connected_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


class AdminBitbucketErrorResponse(BaseModel):
    """Stable integration failures without provider diagnostic material."""

    model_config = ConfigDict(extra="forbid")

    detail: Literal["Bitbucket connection unavailable"]
