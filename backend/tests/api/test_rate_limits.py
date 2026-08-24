"""Endpoint-level contracts for bounded Phase 1 request rates."""

import asyncio
from dataclasses import dataclass, field
from uuid import UUID

import httpx
import pytest

from verboflex.auth.principal import Principal, get_current_principal
from verboflex.auth.rate_limits import get_redis_client
from verboflex.main import app
from verboflex.schemas.users import RoleName


@dataclass
class CountingRedis:
    """Return one deterministic fixed-window counter per call."""

    calls: list[tuple[str, int, tuple[object, ...]]] = field(default_factory=list)

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        self.calls.append((script, numkeys, keys_and_args))
        return [len(self.calls), 60]


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    """Keep limiter state and dependency substitutions isolated by scenario."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


async def _health_requests(count: int) -> list[httpx.Response]:
    """Issue repeated liveness reads from one server-observed client address."""
    transport = httpx.ASGITransport(app=app, client=("192.0.2.10", 44000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return [await client.get("/api/v1/health") for _ in range(count)]


def test_health_allows_sixty_requests_then_blocks_before_handler_work() -> None:
    """Apply the exact inclusive health boundary and stable recovery metadata."""
    responses = asyncio.run(_health_requests(61))

    assert [response.status_code for response in responses[:60]] == [200] * 60
    assert responses[60].status_code == 429
    assert responses[60].json() == {"detail": "Rate limit exceeded"}
    assert int(responses[60].headers["retry-after"]) > 0
    assert responses[60].headers["x-ratelimit-remaining"] == "0"


async def _me_requests(count: int) -> list[httpx.Response]:
    """Issue repeated protected identity reads for one server principal."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return [await client.get("/api/v1/users/me") for _ in range(count)]


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
