"""Authentication request and response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictSchema(BaseModel):
    """Reject unknown JSON fields at the HTTP boundary."""

    model_config = ConfigDict(extra="forbid")


class AccessTokenResponse(StrictSchema):
    """Access-token response shared by login and refresh."""

    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    must_change_password: bool


class ChangePasswordRequest(StrictSchema):
    """Password replacement request."""

    current_password: str
    new_password: str
