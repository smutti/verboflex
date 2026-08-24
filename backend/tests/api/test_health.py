"""Executable contract for the public health endpoint."""

import asyncio

import httpx

from verboflex.main import app


async def request_health() -> httpx.Response:
    """Issue the request directly through the ASGI boundary."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/v1/health")


def test_health_endpoint_is_constant_and_non_sensitive() -> None:
    """Return only the exact approved liveness payload."""
    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
