"""Timeout-bounded, non-leaking service-state aggregation."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from verboflex.schemas.system import ServiceState

ServiceProbe = Callable[[], ServiceState]
_SERVICE_STATES = frozenset({"online", "unavailable", "pending"})


@dataclass(frozen=True, slots=True)
class SystemStatusSnapshot:
    """Safe state projection returned by the probe service."""

    database: ServiceState
    redis: ServiceState
    worker: ServiceState
    checked_at: datetime


class SystemStatusService:
    """Run independent external probes within one strict timeout each."""

    def __init__(
        self,
        *,
        database_probe: ServiceProbe,
        redis_probe: ServiceProbe,
        worker_probe: ServiceProbe,
        timeout_seconds: float,
    ) -> None:
        self._database_probe = database_probe
        self._redis_probe = redis_probe
        self._worker_probe = worker_probe
        self._timeout_seconds = timeout_seconds

    async def collect(self) -> SystemStatusSnapshot:
        """Collect all approved states concurrently without exposing failures."""
        database, redis, worker = await asyncio.gather(
            self._bounded(self._database_probe),
            self._bounded(self._redis_probe),
            self._bounded(self._worker_probe),
        )
        return SystemStatusSnapshot(
            database=database,
            redis=redis,
            worker=worker,
            checked_at=datetime.now(UTC),
        )

    async def _bounded(self, probe: ServiceProbe) -> ServiceState:
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(probe),
                timeout=self._timeout_seconds,
            )
        except Exception:
            return "unavailable"
        if result not in _SERVICE_STATES:
            return "unavailable"
        return result
