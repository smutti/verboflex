"""Endpoint-level contracts for bounded Phase 1 request rates."""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import httpx
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session

from verboflex.api.v1.routes import auth as auth_routes
from verboflex.auth.principal import Principal, get_current_principal
from verboflex.auth.rate_limits import (
    BoundedLocalRateLimiter,
    get_local_rate_limiter,
    get_redis_client,
)
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.schemas.users import RoleName


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
    assert all(isinstance(key, str) for key in keys)
    assert all(str(principal.user_id) not in key for key in keys)


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


def test_system_status_is_rate_limited_before_its_callable_behavior_seam() -> None:
    """Bound diagnostic reads while preserving the dedicated 501 TDD start state."""
    principal = Principal(
        user_id=UUID("00000000-0000-4000-8000-000000000803"),
        email="operator@example.com",
        display_name="Operator Example",
        roles=(RoleName("viewer"),),
        must_change_password=False,
    )
    redis_client = CountingRedis()
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_redis_client] = lambda: redis_client

    responses = asyncio.run(_status_requests(121))

    assert [response.status_code for response in responses[:120]] == [501] * 120
    assert responses[120].status_code == 429
    assert responses[120].json() == {"detail": "Rate limit exceeded"}
    assert responses[120].headers["x-ratelimit-remaining"] == "0"


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
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_redis_client] = lambda: FailingRedis()
    app.dependency_overrides[get_local_rate_limiter] = lambda: local_limiter

    responses = asyncio.run(_status_requests(121))

    assert [response.status_code for response in responses[:120]] == [501] * 120
    assert responses[120].status_code == 429
    assert responses[120].headers["x-ratelimit-remaining"] == "0"


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
