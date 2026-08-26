"""Pure and real-transport contracts for the sample Celery task."""

import os
from dataclasses import dataclass, field
from typing import Any, cast

from pydantic import RedisDsn

from verboflex.core.config import Settings
from verboflex.worker.celery_app import create_celery_app, probe_worker_state
from verboflex.worker.tasks import add

TEST_REDIS_URL = os.environ.get(
    "VERBOFLEX_TEST_CELERY_REDIS_URL",
    "redis://127.0.0.1:56379/0",
)


def test_named_add_task_returns_exactly_five_for_two_and_three() -> None:
    """Keep the deterministic task body independently testable from transport."""
    assert add.name == "verboflex.add"
    assert add.run(2, 3) == 5


def test_add_task_executes_through_redis_and_a_distinct_worker_process() -> None:
    """Queue by public task name and retrieve the worker result within a hard bound."""
    producer = create_celery_app(
        Settings(
            redis_url=RedisDsn(TEST_REDIS_URL),
            service_probe_timeout_seconds=1.0,
        )
    )
    result = producer.send_task("verboflex.add", args=(2, 3))
    try:
        assert result.get(timeout=5) == 5
    finally:
        result.forget()


def test_live_worker_probe_projects_only_online_state() -> None:
    """Prove the public status seam detects the distinct worker without internals."""
    producer = create_celery_app(
        Settings(
            redis_url=RedisDsn(TEST_REDIS_URL),
            service_probe_timeout_seconds=1.0,
        )
    )

    assert probe_worker_state(producer, timeout_seconds=1.0) == "online"


@dataclass
class SilentControl:
    """Model a bounded Celery inspect call with no replying worker."""

    timeouts: list[float] = field(default_factory=list)

    class Inspect:
        def ping(self) -> None:
            return None

    def inspect(self, *, timeout: float) -> Inspect:
        self.timeouts.append(timeout)
        return self.Inspect()


@dataclass
class SilentCelery:
    """Provide only the control surface used by the public worker probe."""

    control: SilentControl = field(default_factory=SilentControl)


def test_worker_probe_maps_no_reply_to_bounded_unavailable_state() -> None:
    """Never expose inspect diagnostics when no worker replies in time."""
    application = SilentCelery()

    state = probe_worker_state(cast(Any, application), timeout_seconds=0.25)

    assert state == "unavailable"
    assert application.control.timeouts == [0.25]
