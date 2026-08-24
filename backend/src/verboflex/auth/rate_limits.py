"""Redis-backed authentication rate-limit seams."""

from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import Depends
from redis import Redis

from verboflex.core.config import Settings, get_settings


class RedisRateLimitClient(Protocol):
    """Minimal Redis capability needed by authentication limits."""

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        """Execute one atomic limiter script."""
        ...


@dataclass(frozen=True, slots=True)
class LoginRateLimit:
    """Observable fixed-window limiter state."""

    allowed: bool
    remaining: int
    retry_after: int


def get_redis_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Redis:
    """Build a decoded synchronous Redis client for request dependencies."""
    return Redis.from_url(str(settings.redis_url), decode_responses=True)


def enforce_login_rate_limit(
    redis_client: RedisRateLimitClient,
    *,
    normalized_email: str,
    client_ip: str,
) -> LoginRateLimit:
    """Count a normalized-email-and-IP login attempt before verification."""
    raise NotImplementedError
