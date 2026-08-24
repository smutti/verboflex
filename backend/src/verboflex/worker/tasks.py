"""Named deterministic work executed only by the Celery worker."""

from verboflex.worker.celery_app import app


@app.task(name="verboflex.add")
def add(left: int, right: int) -> int:
    """Return the deterministic sum used by the out-of-process smoke proof."""
    return left + right
