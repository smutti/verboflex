"""HTTP contracts for the authenticated current-identity projection."""

import asyncio

import httpx

from verboflex.main import app


async def get_me(access_token: str) -> httpx.Response:
    """Call the registered protected route through the ASGI boundary."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )


def test_current_identity_returns_only_the_safe_provider_independent_projection() -> None:
    """Return exact own identity and sorted stable roles without persistence fields."""
    response = asyncio.run(get_me("callable-501-seam"))

    assert response.status_code == 200
    assert response.json() == {
        "id": "00000000-0000-4000-8000-000000000101",
        "email": "person@example.com",
        "display_name": "Person Example",
        "roles": ["admin", "translator"],
        "must_change_password": False,
    }
