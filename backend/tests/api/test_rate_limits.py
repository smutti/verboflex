"""Endpoint-level contracts for bounded Phase 1 request rates."""

import asyncio

import httpx

from verboflex.main import app


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
