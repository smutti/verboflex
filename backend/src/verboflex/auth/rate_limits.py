"""Redis-backed authentication rate-limit seams."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Annotated, Protocol

from fastapi import Depends
from redis import Redis
from redis.exceptions import RedisError

from verboflex.core.config import Settings, get_settings


class RedisRateLimitClient(Protocol):
    """Minimal Redis capability needed by authentication limits."""

    def eval(self, script: str, numkeys: int, *keys_and_args: str) -> object:
        """Execute one atomic limiter script."""
        ...


@dataclass(frozen=True, slots=True)
class LoginRateLimit:
    """Observable fixed-window limiter state."""

    allowed: bool
    remaining: int
    retry_after: int


class RateLimitUnavailable(RuntimeError):
    """Raised when authoritative Redis limiter state cannot be obtained."""


class AuthRateLimited(RuntimeError):
    """Raised before a sensitive authentication action exceeds its window."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("authentication rate limit exceeded")
        self.retry_after = retry_after


LOGIN_LIMIT = 5
LOGIN_WINDOW_SECONDS = 60
REFRESH_LIMIT = 30
LOGOUT_LIMIT = 10
PASSWORD_CHANGE_LIMIT = 10
LOGIN_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


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
    identity_digest = sha256(f"{normalized_email}\0{client_ip}".encode()).hexdigest()
    key = f"verboflex:auth:login:{identity_digest}"
    try:
        raw_result = redis_client.eval(
            LOGIN_RATE_LIMIT_SCRIPT,
            1,
            key,
            str(LOGIN_WINDOW_SECONDS),
        )
        if not isinstance(raw_result, (list, tuple)) or len(raw_result) != 2:
            raise RateLimitUnavailable("login rate limiter returned invalid state")
        attempts = int(raw_result[0])
        ttl = int(raw_result[1])
    except (RedisError, TypeError, ValueError) as error:
        raise RateLimitUnavailable("login rate limiter is unavailable") from error

    retry_after = max(ttl, 1)
    return LoginRateLimit(
        allowed=attempts <= LOGIN_LIMIT,
        remaining=max(LOGIN_LIMIT - attempts, 0),
        retry_after=retry_after,
    )


def enforce_auth_action_rate_limit(
    redis_client: RedisRateLimitClient,
    *,
    action: str,
    identity: str,
    client_ip: str,
    limit: int,
) -> LoginRateLimit:
    """Count a sensitive auth action without exposing its raw authority in Redis."""
    identity_digest = sha256(f"{identity}\0{client_ip}".encode()).hexdigest()
    key = f"verboflex:auth:{action}:{identity_digest}"
    try:
        raw_result = redis_client.eval(
            LOGIN_RATE_LIMIT_SCRIPT,
            1,
            key,
            str(LOGIN_WINDOW_SECONDS),
        )
        if not isinstance(raw_result, (list, tuple)) or len(raw_result) != 2:
            raise RateLimitUnavailable(f"{action} rate limiter returned invalid state")
        attempts = int(raw_result[0])
        ttl = int(raw_result[1])
    except (RedisError, TypeError, ValueError) as error:
        raise RateLimitUnavailable(f"{action} rate limiter is unavailable") from error

    retry_after = max(ttl, 1)
    return LoginRateLimit(
        allowed=attempts <= limit,
        remaining=max(limit - attempts, 0),
        retry_after=retry_after,
    )
