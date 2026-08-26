"""Endpoint-level contracts for bounded Phase 1 request rates."""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException, Request
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session

from verboflex.api.v1.routes import auth as auth_routes
from verboflex.api.v1.routes.system import get_system_status_service
from verboflex.auth import rate_limits
from verboflex.auth.principal import Principal, get_current_principal
from verboflex.auth.rate_limits import (
    BoundedLocalRateLimiter,
    LoginRateLimit,
    RateLimitUnavailable,
    enforce_auth_action_rate_limit,
    enforce_health_rate_limit,
    enforce_login_rate_limit,
    enforce_ordinary_read_rate_limit,
    get_local_rate_limiter,
    get_redis_client,
    raise_rate_limited,
)
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.schemas.system import ServiceState
from verboflex.schemas.users import RoleName
from verboflex.services.system_status import SystemStatusService


@dataclass
class CountingRedis:
    """Return one deterministic fixed-window counter per call."""

    calls: list[tuple[str, int, tuple[object, ...]]] = field(default_factory=list)

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        self.calls.append((script, numkeys, keys_and_args))
        return [len(self.calls), 60]


class FailingRedis:
    """Model a Redis outage at the atomic counter boundary."""

    def eval(self, _script: str, _numkeys: int, *_args: object) -> object:
        raise RedisConnectionError("redis unavailable at 10.0.0.5:6379")


@dataclass
class FakeClock:
    """Controllable monotonic clock for exact reset boundaries."""

    now: float = 1000.0

    def __call__(self) -> float:
        return self.now


@dataclass
class ProbeCounter:
    """Count real status-probe invocations behind the rate boundary."""

    calls: int = 0

    def online(self) -> ServiceState:
        self.calls += 1
        return "online"


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    """Keep limiter state and dependency substitutions isolated by scenario."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


async def _health_requests(
    count: int,
    *,
    forwarded_ips: bool = False,
) -> list[httpx.Response]:
    """Issue repeated liveness reads from one server-observed client address."""
    transport = httpx.ASGITransport(app=app, client=("192.0.2.10", 44000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return [
            await client.get(
                "/api/v1/health",
                headers={"X-Forwarded-For": f"198.51.100.{index % 250 + 1}"}
                if forwarded_ips
                else None,
            )
            for index in range(count)
        ]


def test_health_allows_sixty_requests_then_blocks_before_handler_work() -> None:
    """Apply the exact inclusive health boundary and stable recovery metadata."""
    limiter = BoundedLocalRateLimiter()
    app.dependency_overrides[get_local_rate_limiter] = lambda: limiter
    responses = asyncio.run(_health_requests(61))

    assert [response.status_code for response in responses[:60]] == [200] * 60
    assert responses[60].status_code == 429
    assert responses[60].json() == {"detail": "Rate limit exceeded"}
    assert int(responses[60].headers["retry-after"]) > 0
    assert responses[60].headers["x-ratelimit-remaining"] == "0"


def test_health_resets_at_the_exact_window_boundary() -> None:
    """Permit a new request when the complete fixed window has elapsed."""
    clock = FakeClock()
    limiter = BoundedLocalRateLimiter(clock=clock)
    app.dependency_overrides[get_local_rate_limiter] = lambda: limiter
    assert asyncio.run(_health_requests(60))[-1].status_code == 200
    assert asyncio.run(_health_requests(1))[0].status_code == 429

    clock.now += 60

    reset_response = asyncio.run(_health_requests(1))[0]
    assert reset_response.status_code == 200
    assert reset_response.json() == {"status": "ok"}


def test_health_ignores_untrusted_forwarded_ip_headers() -> None:
    """Do not let callers rotate limiter keys through proxy-shaped headers."""
    limiter = BoundedLocalRateLimiter()
    app.dependency_overrides[get_local_rate_limiter] = lambda: limiter

    responses = asyncio.run(_health_requests(61, forwarded_ips=True))

    assert responses[60].status_code == 429
    assert responses[60].headers["x-ratelimit-remaining"] == "0"


def test_local_fallback_evicts_oldest_actor_at_its_cardinality_ceiling() -> None:
    """Keep outage fallback memory bounded even when actor keys churn."""
    limiter = BoundedLocalRateLimiter(max_keys=2)
    assert limiter.check("actor-a", limit=1, window_seconds=60).allowed is True
    assert limiter.check("actor-a", limit=1, window_seconds=60).allowed is False

    assert limiter.check("actor-b", limit=1, window_seconds=60).allowed is True
    assert limiter.check("actor-c", limit=1, window_seconds=60).allowed is True

    assert limiter.check("actor-a", limit=1, window_seconds=60).allowed is True


def test_local_fallback_rejects_invalid_capacity_and_policy_values() -> None:
    """Fail closed instead of accepting nonsensical or unbounded local policies."""
    with pytest.raises(ValueError, match="max_keys must be positive"):
        BoundedLocalRateLimiter(max_keys=0)

    limiter = BoundedLocalRateLimiter()
    with pytest.raises(ValueError, match="rate policy values must be positive"):
        limiter.check("actor", limit=0, window_seconds=60)
    with pytest.raises(ValueError, match="rate policy values must be positive"):
        limiter.check("actor", limit=1, window_seconds=0)


async def _me_requests(count: int) -> list[httpx.Response]:
    """Issue repeated protected identity reads for one server principal."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return [await client.get("/api/v1/users/me") for _ in range(count)]


async def _status_requests(count: int) -> list[httpx.Response]:
    """Issue repeated status reads while the callable behavior seam remains 501."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return [await client.get("/api/v1/system/status") for _ in range(count)]


async def _login_from_unvalidated_peer() -> httpx.Response:
    """Submit login from a malformed peer plus a caller-controlled proxy header."""
    transport = httpx.ASGITransport(app=app, client=("not-an-ip", 44000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            "/api/v1/auth/token",
            data={"username": "PERSON@EXAMPLE.COM", "password": "long password phrase"},
            headers={"X-Forwarded-For": "203.0.113.99"},
        )


def test_current_user_read_allows_one_hundred_twenty_then_blocks() -> None:
    """Derive the ordinary-read key from authenticated server authority."""
    principal = Principal(
        user_id=UUID("00000000-0000-4000-8000-000000000801"),
        email="person@example.com",
        display_name="Person Example",
        roles=(RoleName("viewer"),),
        must_change_password=False,
    )
    redis_client = CountingRedis()
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_redis_client] = lambda: redis_client

    responses = asyncio.run(_me_requests(121))

    assert [response.status_code for response in responses[:120]] == [200] * 120
    assert responses[120].status_code == 429
    assert responses[120].json() == {"detail": "Rate limit exceeded"}
    assert int(responses[120].headers["retry-after"]) > 0
    assert responses[120].headers["x-ratelimit-remaining"] == "0"
    keys = [call[2][0] for call in redis_client.calls]
    for key in keys:
        assert isinstance(key, str)
        assert str(principal.user_id) not in key


def test_current_user_read_uses_bounded_local_limit_when_redis_is_unavailable() -> None:
    """Keep ordinary reads usable but still bounded during a Redis outage."""
    principal = Principal(
        user_id=UUID("00000000-0000-4000-8000-000000000802"),
        email="reader@example.com",
        display_name="Reader Example",
        roles=(RoleName("viewer"),),
        must_change_password=False,
    )
    local_limiter = BoundedLocalRateLimiter(max_keys=4)
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_redis_client] = lambda: FailingRedis()
    app.dependency_overrides[get_local_rate_limiter] = lambda: local_limiter

    responses = asyncio.run(_me_requests(121))

    assert [response.status_code for response in responses[:120]] == [200] * 120
    assert responses[120].status_code == 429
    assert responses[120].json() == {"detail": "Rate limit exceeded"}
    assert responses[120].headers["x-ratelimit-remaining"] == "0"


def test_system_status_is_rate_limited_before_probe_work() -> None:
    """Reject request 121 without executing any of the three service probes."""
    principal = Principal(
        user_id=UUID("00000000-0000-4000-8000-000000000803"),
        email="operator@example.com",
        display_name="Operator Example",
        roles=(RoleName("viewer"),),
        must_change_password=False,
    )
    redis_client = CountingRedis()
    probes = ProbeCounter()
    service = SystemStatusService(
        database_probe=probes.online,
        redis_probe=probes.online,
        worker_probe=probes.online,
        timeout_seconds=0.1,
    )
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_redis_client] = lambda: redis_client
    app.dependency_overrides[get_system_status_service] = lambda: service

    responses = asyncio.run(_status_requests(121))

    assert [response.status_code for response in responses[:120]] == [200] * 120
    assert responses[120].status_code == 429
    assert responses[120].json() == {"detail": "Rate limit exceeded"}
    assert responses[120].headers["x-ratelimit-remaining"] == "0"
    assert probes.calls == 120 * 3


def test_system_status_keeps_a_bounded_local_limit_during_redis_outage() -> None:
    """Keep diagnostics reachable without making Redis failure an unbounded bypass."""
    principal = Principal(
        user_id=UUID("00000000-0000-4000-8000-000000000804"),
        email="diagnostic@example.com",
        display_name="Diagnostic Example",
        roles=(RoleName("viewer"),),
        must_change_password=False,
    )
    local_limiter = BoundedLocalRateLimiter(max_keys=4)
    probes = ProbeCounter()
    service = SystemStatusService(
        database_probe=probes.online,
        redis_probe=probes.online,
        worker_probe=probes.online,
        timeout_seconds=0.1,
    )
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_redis_client] = lambda: FailingRedis()
    app.dependency_overrides[get_local_rate_limiter] = lambda: local_limiter
    app.dependency_overrides[get_system_status_service] = lambda: service

    responses = asyncio.run(_status_requests(121))

    assert [response.status_code for response in responses[:120]] == [200] * 120
    assert responses[120].status_code == 429
    assert responses[120].headers["x-ratelimit-remaining"] == "0"
    assert probes.calls == 120 * 3


def test_login_uses_only_a_validated_server_observed_client_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalize an invalid peer to one bounded key and ignore forwarded headers."""
    observed_ips: list[str] = []

    def observe_authentication(
        _session: Session,
        _redis_client: object,
        *,
        email: str,
        password: str,
        client_ip: str,
        settings: Settings,
    ) -> object:
        del email, password, settings
        observed_ips.append(client_ip)
        return SimpleNamespace(
            access_token="signed-access-token",
            refresh_token=None,
            expires_in=300,
            must_change_password=True,
        )

    monkeypatch.setattr(auth_routes, "authenticate_login", observe_authentication)
    app.dependency_overrides[get_db_session] = lambda: cast(Session, object())
    app.dependency_overrides[get_redis_client] = lambda: CountingRedis()
    app.dependency_overrides[get_settings] = lambda: Settings(refresh_cookie_secure=False)

    response = asyncio.run(_login_from_unvalidated_peer())

    assert response.status_code == 200
    assert observed_ips == ["unknown"]


def test_local_limiter_accepts_exact_minima_and_reports_exact_window_state() -> None:
    """Keep inclusive one-key/one-second policies and exact counter metadata."""
    clock = FakeClock()
    limiter = BoundedLocalRateLimiter(max_keys=1, clock=clock)

    first = limiter.check("actor", limit=2, window_seconds=1)
    clock.now += 0.25
    second = limiter.check("actor", limit=2, window_seconds=1)
    clock.now += 0.25
    third = limiter.check("actor", limit=2, window_seconds=1)
    fourth = limiter.check("actor", limit=2, window_seconds=1)

    assert first == LoginRateLimit(allowed=True, remaining=1, retry_after=1)
    assert second == LoginRateLimit(allowed=True, remaining=0, retry_after=1)
    assert third == LoginRateLimit(allowed=False, remaining=0, retry_after=1)
    assert fourth == LoginRateLimit(allowed=False, remaining=0, retry_after=1)

    long_window = BoundedLocalRateLimiter(clock=FakeClock())
    assert long_window.check("actor", limit=1, window_seconds=10).retry_after == 10


def test_rate_limit_exception_preserves_exact_metadata_keys() -> None:
    """Expose canonical recovery header names at the direct dependency seam."""
    with pytest.raises(HTTPException) as error:
        raise_rate_limited(LoginRateLimit(allowed=False, remaining=0, retry_after=7))

    assert error.value.status_code == 429
    assert error.value.detail == "Rate limit exceeded"
    assert error.value.headers == {
        "Retry-After": "7",
        "X-RateLimit-Remaining": "0",
    }


def test_health_limit_uses_the_validated_peer_in_its_exact_key() -> None:
    """Prevent anonymous health traffic from collapsing into one shared counter."""
    calls: list[tuple[object, int, int]] = []

    class RecordingLimiter:
        def check(self, key: object, *, limit: int, window_seconds: int) -> LoginRateLimit:
            calls.append((key, limit, window_seconds))
            return LoginRateLimit(allowed=True, remaining=59, retry_after=60)

    request = Request({"type": "http", "client": ("192.0.2.44", 44000)})
    enforce_health_rate_limit(request, cast(BoundedLocalRateLimiter, RecordingLimiter()))

    assert calls == [("health:192.0.2.44", 60, 60)]


def test_missing_server_peer_projects_to_one_bounded_unknown_identity() -> None:
    """Treat absent ASGI client metadata as the same safe unknown actor."""
    request = Request({"type": "http", "client": None})

    assert rate_limits.validated_client_ip(request) == "unknown"


def test_redis_client_applies_both_bounded_socket_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never let Redis connection or read work exceed the service probe bound."""
    observed: dict[str, object] = {}
    sentinel = object()

    def observe_from_url(url: str, **kwargs: object) -> object:
        observed["url"] = url
        observed.update(kwargs)
        return sentinel

    monkeypatch.setattr(rate_limits.Redis, "from_url", staticmethod(observe_from_url))
    settings = Settings(refresh_cookie_secure=False, service_probe_timeout_seconds=0.75)

    result = get_redis_client(settings)

    assert result is sentinel
    assert observed == {
        "url": str(settings.redis_url),
        "decode_responses": True,
        "socket_connect_timeout": 0.75,
        "socket_timeout": 0.75,
    }


@pytest.mark.parametrize("raw_result", [None, [1], [1, 2, 3]])
def test_login_limiter_rejects_invalid_redis_state_with_exact_error(raw_result: object) -> None:
    """Keep malformed shared counter state distinct from transport failure."""
    redis_client = CountingRedis()
    redis_client.eval = lambda *_args: raw_result  # type: ignore[method-assign]

    with pytest.raises(RateLimitUnavailable) as error:
        enforce_login_rate_limit(
            redis_client,
            normalized_email="person@example.com",
            client_ip="192.0.2.1",
        )

    assert error.value.args == ("login rate limiter returned invalid state",)


def test_login_limiter_maps_transport_failure_to_exact_error() -> None:
    """Keep Redis diagnostics out of the stable limiter failure surface."""
    with pytest.raises(RateLimitUnavailable) as error:
        enforce_login_rate_limit(
            FailingRedis(),
            normalized_email="person@example.com",
            client_ip="192.0.2.1",
        )

    assert error.value.args == ("login rate limiter is unavailable",)


@pytest.mark.parametrize("raw_result", [None, [1], [1, 2, 3]])
def test_action_limiter_rejects_invalid_redis_state_with_action_context(
    raw_result: object,
) -> None:
    """Name the failed sensitive action without exposing actor authority."""
    redis_client = CountingRedis()
    redis_client.eval = lambda *_args: raw_result  # type: ignore[method-assign]

    with pytest.raises(RateLimitUnavailable) as error:
        enforce_auth_action_rate_limit(
            redis_client,
            action="refresh",
            identity="opaque-user",
            client_ip="192.0.2.1",
            limit=30,
        )

    assert error.value.args == ("refresh rate limiter returned invalid state",)


def test_action_limiter_maps_transport_failure_with_action_context() -> None:
    """Preserve the action name while redacting the Redis transport diagnostic."""
    with pytest.raises(RateLimitUnavailable) as error:
        enforce_auth_action_rate_limit(
            FailingRedis(),
            action="logout",
            identity="opaque-user",
            client_ip="192.0.2.1",
            limit=10,
        )

    assert error.value.args == ("logout rate limiter is unavailable",)


def test_ordinary_read_forwards_exact_server_owned_rate_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Derive the Redis action and actor dimensions solely from current authority."""
    observed: dict[str, object] = {}
    expected = LoginRateLimit(allowed=True, remaining=119, retry_after=60)

    def observe_action(
        redis_client: object,
        *,
        action: str,
        identity: str,
        client_ip: str,
        limit: int,
    ) -> LoginRateLimit:
        observed.update(
            redis_client=redis_client,
            action=action,
            identity=identity,
            client_ip=client_ip,
            limit=limit,
        )
        return expected

    redis_client = object()
    monkeypatch.setattr(rate_limits, "enforce_auth_action_rate_limit", observe_action)

    result = enforce_ordinary_read_rate_limit(
        cast(rate_limits.RedisRateLimitClient, redis_client),
        BoundedLocalRateLimiter(),
        user_id="user-123",
    )

    assert result == expected
    assert observed == {
        "redis_client": redis_client,
        "action": "ordinary-read",
        "identity": "user-123",
        "client_ip": "server-principal",
        "limit": 120,
    }


def test_ordinary_read_fallback_uses_exact_local_actor_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep Redis outage fallback isolated per authenticated user."""
    calls: list[tuple[object, int, int]] = []
    expected = LoginRateLimit(allowed=True, remaining=119, retry_after=60)

    def fail_action(*_args: object, **_kwargs: object) -> LoginRateLimit:
        raise RateLimitUnavailable("unavailable")

    class RecordingLimiter:
        def check(self, key: object, *, limit: int, window_seconds: int) -> LoginRateLimit:
            calls.append((key, limit, window_seconds))
            return expected

    monkeypatch.setattr(rate_limits, "enforce_auth_action_rate_limit", fail_action)

    result = enforce_ordinary_read_rate_limit(
        cast(rate_limits.RedisRateLimitClient, object()),
        cast(BoundedLocalRateLimiter, RecordingLimiter()),
        user_id="user-456",
    )

    assert result == expected
    assert calls == [("ordinary-read:user-456", 120, 60)]
