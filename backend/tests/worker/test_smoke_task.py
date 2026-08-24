"""Pure and real-transport contracts for the sample Celery task."""

import os

from pydantic import RedisDsn

from verboflex.core.config import Settings
from verboflex.worker.celery_app import create_celery_app
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
            refresh_cookie_secure=False,
            service_probe_timeout_seconds=1.0,
        )
    )
    result = producer.send_task("verboflex.add", args=(2, 3))
    try:
        assert result.get(timeout=5) == 5
    finally:
        result.forget()
