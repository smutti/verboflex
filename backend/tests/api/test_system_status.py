"""Authenticated non-leaking contracts for bounded service status."""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

import httpx
import pytest

from verboflex.auth.principal import Principal, get_current_principal
from verboflex.auth.rate_limits import get_redis_client
from verboflex.main import app
from verboflex.schemas.users import RoleName


@dataclass
class AvailableRedis:
    """Permit the ordinary-read limiter without touching external Redis."""

    calls: list[tuple[str, int, tuple[object, ...]]] = field(default_factory=list)

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        self.calls.append((script, numkeys, keys_and_args))
        return [len(self.calls), 60]


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    """Isolate service status dependencies per contract scenario."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def ordinary_principal() -> Principal:
    """Return one provider-independent ordinary authority."""
    return Principal(
        user_id=UUID("00000000-0000-4000-8000-000000000811"),
        email="operator@example.com",
        display_name="Operator Example",
        roles=(RoleName("viewer"),),
        must_change_password=False,
    )


async def request_status() -> httpx.Response:
    """Call the registered status route through the ASGI boundary."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/v1/system/status")


def test_ordinary_user_receives_only_the_exact_service_status_projection() -> None:
    """Replace the callable 501 seam with the approved bounded JSON contract."""
    app.dependency_overrides[get_current_principal] = ordinary_principal
    app.dependency_overrides[get_redis_client] = lambda: AvailableRedis()

    response = asyncio.run(request_status())

    assert response.status_code == 200
    assert set(response.json()) == {"api", "database", "redis", "worker", "checked_at"}
    assert response.json()["api"] == "online"
    assert response.json()["database"] in {"online", "unavailable", "pending"}
    assert response.json()["redis"] in {"online", "unavailable", "pending"}
    assert response.json()["worker"] in {"online", "unavailable", "pending"}
    checked_at = datetime.fromisoformat(response.json()["checked_at"].replace("Z", "+00:00"))
    assert checked_at.tzinfo is not None
