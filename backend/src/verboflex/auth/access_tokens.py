"""Signed short-lived access authority seams."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from verboflex.core.config import Settings

TokenPurpose = Literal["access", "password_change"]


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Validated provider-independent authority carried by a bearer token."""

    user_id: UUID
    session_id: UUID | None
    issued_at: datetime
    expires_at: datetime
    purpose: TokenPurpose
    token_version: int


def issue_access_token(
    *,
    user_id: UUID,
    token_version: int,
    purpose: TokenPurpose,
    settings: Settings,
    session_id: UUID | None = None,
    now: datetime | None = None,
) -> str:
    """Issue signed authority with the approved purpose-specific lifetime."""
    raise NotImplementedError


def decode_access_token(
    token: str,
    *,
    settings: Settings,
    expected_purpose: TokenPurpose = "access",
) -> AccessTokenClaims:
    """Verify and decode one bearer token for the expected authority purpose."""
    raise NotImplementedError
