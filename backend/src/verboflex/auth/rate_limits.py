"""Redis-backed and bounded process-local request-rate seams."""

import math
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from ipaddress import ip_address
from threading import Lock
from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, Request, status
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


LOGIN_LIMIT = 5
LOGIN_WINDOW_SECONDS = 60
REFRESH_LIMIT = 30
LOGOUT_LIMIT = 10
PASSWORD_CHANGE_LIMIT = 10
HEALTH_LIMIT = 60
ORDINARY_READ_LIMIT = 120
LOCAL_RATE_LIMIT_MAX_KEYS = 2048
LOGIN_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


@dataclass(frozen=True, slots=True)
class _LocalWindow:
    """One bounded fixed-window counter."""

    started_at: float
    attempts: int


class BoundedLocalRateLimiter:
    """Thread-safe fixed windows with a strict actor-cardinality ceiling."""

    def __init__(
        self,
        *,
        max_keys: int = LOCAL_RATE_LIMIT_MAX_KEYS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_keys < 1:
            raise ValueError("max_keys must be positive")
        self._max_keys = max_keys
        self._clock = clock
        self._windows: OrderedDict[str, _LocalWindow] = OrderedDict()
        self._lock = Lock()

    def check(self, key: str, *, limit: int, window_seconds: int) -> LoginRateLimit:
        """Count one request without allowing unbounded process memory growth."""
        if limit < 1 or window_seconds < 1:
            raise ValueError("rate policy values must be positive")
        now = self._clock()
        with self._lock:
            current = self._windows.get(key)
            if current is None or now >= current.started_at + window_seconds:
                if current is None and len(self._windows) >= self._max_keys:
                    self._windows.popitem(last=False)
                current = _LocalWindow(started_at=now, attempts=1)
            else:
                current = _LocalWindow(
                    started_at=current.started_at,
                    attempts=current.attempts + 1,
                )
            self._windows[key] = current
            self._windows.move_to_end(key)

        retry_after = max(math.ceil(current.started_at + window_seconds - now), 1)
        return LoginRateLimit(
            allowed=current.attempts <= limit,
            remaining=max(limit - current.attempts, 0),
            retry_after=retry_after,
        )


_local_rate_limiter = BoundedLocalRateLimiter()


def get_local_rate_limiter() -> BoundedLocalRateLimiter:
    """Return the bounded process-local diagnostic limiter."""
    return _local_rate_limiter


def validated_client_ip(request: Request) -> str:
    """Return only the server-observed, syntactically valid peer address."""
    candidate = request.client.host if request.client is not None else ""
    try:
        return str(ip_address(candidate))
    except ValueError:
        return "unknown"


def raise_rate_limited(result: LoginRateLimit) -> None:
    """Raise the one stable Phase 1 exhaustion response."""
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded",
        headers={
            "Retry-After": str(result.retry_after),
            "X-RateLimit-Remaining": "0",
        },
    )


def enforce_health_rate_limit(
    request: Request,
    limiter: Annotated[BoundedLocalRateLimiter, Depends(get_local_rate_limiter)],
) -> None:
    """Bound anonymous liveness reads by the validated network peer."""
    result = limiter.check(
        f"health:{validated_client_ip(request)}",
        limit=HEALTH_LIMIT,
        window_seconds=LOGIN_WINDOW_SECONDS,
    )
    if not result.allowed:
        raise_rate_limited(result)


def get_redis_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Redis:
    """Build a decoded synchronous Redis client for request dependencies."""
    return Redis.from_url(
        str(settings.redis_url),
        decode_responses=True,
        socket_connect_timeout=settings.service_probe_timeout_seconds,
        socket_timeout=settings.service_probe_timeout_seconds,
    )


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


def enforce_ordinary_read_rate_limit(
    redis_client: RedisRateLimitClient,
    local_limiter: BoundedLocalRateLimiter,
    *,
    user_id: str,
) -> LoginRateLimit:
    """Prefer shared Redis state and retain a bounded diagnostic fallback."""
    try:
        return enforce_auth_action_rate_limit(
            redis_client,
            action="ordinary-read",
            identity=user_id,
            client_ip="server-principal",
            limit=ORDINARY_READ_LIMIT,
        )
    except RateLimitUnavailable:
        return local_limiter.check(
            f"ordinary-read:{user_id}",
            limit=ORDINARY_READ_LIMIT,
            window_seconds=LOGIN_WINDOW_SECONDS,
        )
