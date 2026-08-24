"""Pure and real-transport contracts for the sample Celery task."""

from verboflex.worker.tasks import add


def test_named_add_task_returns_exactly_five_for_two_and_three() -> None:
    """Keep the deterministic task body independently testable from transport."""
    assert add.name == "verboflex.add"
    assert add.run(2, 3) == 5
