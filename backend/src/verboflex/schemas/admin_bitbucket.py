"""Closed administrator contracts for the organizational Bitbucket connection."""

from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict


class AdminBitbucketAuthorizationResponse(BaseModel):
    """One short-lived authorization destination without provider credentials."""

    model_config = ConfigDict(extra="forbid")

    authorization_url: AnyHttpUrl
    state_expires_in: Literal[600]


class AdminBitbucketStatusResponse(BaseModel):
    """Bounded connection state safe for browser projection."""

    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "Disconnected",
        "Connected",
        "Reauthorization required",
        "Unavailable",
    ]
    scope_profile: Literal["repository"] = "repository"
    scope_label: Literal["Read-only repository access"] = "Read-only repository access"
    connected_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


class AdminBitbucketErrorResponse(BaseModel):
    """Stable integration failures without provider diagnostic material."""

    model_config = ConfigDict(extra="forbid")

    detail: Literal["OAuth callback rejected", "Bitbucket connection unavailable"]
