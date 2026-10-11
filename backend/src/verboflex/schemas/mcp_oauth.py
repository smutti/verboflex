"""Bounded OAuth wire contracts and authenticated consent contracts."""

from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from verboflex.core.text import StorableText

READ_SCOPE = "verboflex:read"
WRITE_SCOPE = "verboflex:write"
SCOPES = (READ_SCOPE, WRITE_SCOPE)
ShortText = Annotated[str, Field(min_length=1, max_length=2048)]


def validate_redirect(value: str) -> str:
    url = urlsplit(value)
    _ = url.port
    if (
        len(value) > 2048
        or any(ord(char) <= 32 for char in value)
        or url.scheme not in {"https", "http"}
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or url.fragment
        or (url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"})
    ):
        raise ValueError("Redirect must use HTTPS or an exact loopback HTTP address")
    return value


class RegisterMcpClient(BaseModel):
    # OAuth registration permits extension fields; never fetch client_uri/logo_uri/JWKS.
    model_config = ConfigDict(extra="ignore")
    client_name: Annotated[StorableText, Field(min_length=1, max_length=128)] = "MCP client"
    redirect_uris: Annotated[list[ShortText], Field(min_length=1, max_length=10)]
    token_endpoint_auth_method: Literal["none", "client_secret_post", "client_secret_basic"] = (
        "none"
    )
    grant_types: list[Literal["authorization_code", "refresh_token"]] = [
        "authorization_code",
        "refresh_token",
    ]
    response_types: Annotated[list[Literal["code"]], Field(min_length=1, max_length=1)] = ["code"]
    scope: Annotated[str | None, Field(max_length=64)] = None

    @field_validator("grant_types")
    @classmethod
    def grants(cls, values: list[str]) -> list[str]:
        if "authorization_code" not in values or len(values) > 2:
            raise ValueError("Authorization code grant is required")
        return list(dict.fromkeys(values))

    @field_validator("redirect_uris")
    @classmethod
    def redirects(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(validate_redirect(value) for value in values))


class McpConsentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow: bool
    allow_write: bool = False
