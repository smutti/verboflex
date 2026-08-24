"""Internal credential-exchange seams."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from verboflex.auth.rate_limits import RedisRateLimitClient
from verboflex.core.config import Settings


@dataclass(frozen=True, slots=True)
class LoginAuthority:
    """Authority and optional refresh material returned by a valid login."""

    access_token: str
    expires_in: int
    must_change_password: bool
    refresh_token: str | None


def authenticate_login(
    session: Session,
    redis_client: RedisRateLimitClient,
    *,
    email: str,
    password: str,
    client_ip: str,
    settings: Settings,
) -> LoginAuthority:
    """Authenticate one internal account after enforcing its Redis limit."""
    raise NotImplementedError
