"""Authenticated non-leaking contracts for bounded service status."""

import asyncio
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import cast
from uuid import UUID

import httpx
import pytest

from verboflex.api.v1.routes.system import get_system_status_service
from verboflex.auth.principal import Principal, get_current_principal
from verboflex.auth.rate_limits import get_redis_client
from verboflex.main import app
from verboflex.schemas.system import ServiceState
from verboflex.schemas.users import RoleName
from verboflex.services.system_status import SystemStatusService


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


async def request_status_with_elapsed() -> tuple[httpx.Response, float]:
    """Measure response latency before the test event loop drains worker threads."""
    started_at = time.perf_counter()
    response = await request_status()
    return response, time.perf_counter() - started_at


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


def test_probe_exceptions_and_invalid_values_map_to_non_leaking_unavailable() -> None:
    """Never project raw diagnostics, addresses, exceptions, or task identifiers."""

    def failing_database_probe() -> ServiceState:
        raise RuntimeError("postgresql://admin:secret@db.internal:5432/verboflex")

    service = SystemStatusService(
        database_probe=failing_database_probe,
        redis_probe=lambda: cast(ServiceState, "redis://cache.internal:6379/0"),
        worker_probe=lambda: "pending",
        timeout_seconds=0.1,
    )
    app.dependency_overrides[get_current_principal] = ordinary_principal
    app.dependency_overrides[get_redis_client] = lambda: AvailableRedis()
    app.dependency_overrides[get_system_status_service] = lambda: service

    response = asyncio.run(request_status())

    assert response.status_code == 200
    assert response.json()["database"] == "unavailable"
    assert response.json()["redis"] == "unavailable"
    assert response.json()["worker"] == "pending"
    serialized = response.text.casefold()
    for forbidden in (
        "postgresql",
        "redis://",
        "admin",
        "secret",
        "internal",
        "5432",
        "6379",
        "traceback",
        "task_id",
    ):
        assert forbidden not in serialized


def test_every_slow_probe_is_independently_timeout_bounded() -> None:
    """Return all unavailable states within one timeout budget, not three serial waits."""

    def slow_probe() -> ServiceState:
        time.sleep(0.2)
        return "online"

    service = SystemStatusService(
        database_probe=slow_probe,
        redis_probe=slow_probe,
        worker_probe=slow_probe,
        timeout_seconds=0.02,
    )
    app.dependency_overrides[get_current_principal] = ordinary_principal
    app.dependency_overrides[get_redis_client] = lambda: AvailableRedis()
    app.dependency_overrides[get_system_status_service] = lambda: service

    response, elapsed = asyncio.run(request_status_with_elapsed())

    assert response.status_code == 200
    assert response.json()["database"] == "unavailable"
    assert response.json()["redis"] == "unavailable"
    assert response.json()["worker"] == "unavailable"
    assert elapsed < 0.1
