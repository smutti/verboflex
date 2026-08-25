"""Authentication request and response contracts."""

from typing import Annotated, Literal

from fastapi import Form
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, Field

from verboflex.auth.passwords import MAX_PASSWORD_CHARACTERS

MAX_LOGIN_IDENTIFIER_CHARACTERS = 320
MAX_OAUTH_SCOPE_CHARACTERS = 1024


class StrictSchema(BaseModel):
    """Reject unknown JSON fields at the HTTP boundary."""

    model_config = ConfigDict(extra="forbid")


class AccessTokenResponse(StrictSchema):
    """Access-token response shared by login and refresh."""

    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    must_change_password: bool


class BoundedOAuth2PasswordRequestForm(OAuth2PasswordRequestForm):
    """OAuth2 password form with bounded credential parsing at the HTTP edge."""

    def __init__(
        self,
        *,
        grant_type: Annotated[str | None, Form(pattern="^password$")] = None,
        username: Annotated[
            str,
            Form(max_length=MAX_LOGIN_IDENTIFIER_CHARACTERS),
        ],
        password: Annotated[
            str,
            Form(
                max_length=MAX_PASSWORD_CHARACTERS,
                json_schema_extra={"format": "password"},
            ),
        ],
        scope: Annotated[str, Form(max_length=MAX_OAUTH_SCOPE_CHARACTERS)] = "",
        client_id: Annotated[
            str | None,
            Form(max_length=MAX_LOGIN_IDENTIFIER_CHARACTERS),
        ] = None,
        client_secret: Annotated[
            str | None,
            Form(
                max_length=MAX_PASSWORD_CHARACTERS,
                json_schema_extra={"format": "password"},
            ),
        ] = None,
    ) -> None:
        super().__init__(
            grant_type=grant_type,
            username=username,
            password=password,
            scope=scope,
            client_id=client_id,
            client_secret=client_secret,
        )


class ChangePasswordRequest(StrictSchema):
    """Password replacement request."""

    current_password: Annotated[
        str,
        Field(
            json_schema_extra={
                "format": "password",
                "maxLength": MAX_PASSWORD_CHARACTERS,
            }
        ),
    ]
    new_password: Annotated[
        str,
        Field(
            json_schema_extra={
                "format": "password",
                "maxLength": MAX_PASSWORD_CHARACTERS,
            }
        ),
    ]
