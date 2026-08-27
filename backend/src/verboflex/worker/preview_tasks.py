"""UUID-only Celery execution for durable preview attempts."""

from uuid import UUID

from billiard.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]

from verboflex.db.session import SessionFactory
from verboflex.services.preview_jobs import (
    PREVIEW_HARD_TIME_LIMIT_SECONDS,
    PREVIEW_SOFT_TIME_LIMIT_SECONDS,
    PreviewJobIdentity,
    PreviewJobTimedOut,
    PreviewProcessor,
    execute_preview_job,
    skeleton_preview_processor,
)
from verboflex.worker.celery_app import app

preview_processor: PreviewProcessor = skeleton_preview_processor


def _bounded_processor(identity: PreviewJobIdentity) -> dict[str, object]:
    try:
        return dict(preview_processor(identity))
    except SoftTimeLimitExceeded as error:
        raise PreviewJobTimedOut from error


@app.task(
    name="verboflex.preview.run",
    soft_time_limit=PREVIEW_SOFT_TIME_LIMIT_SECONDS,
    time_limit=PREVIEW_HARD_TIME_LIMIT_SECONDS,
    serializer="json",
    ignore_result=True,
)  # type: ignore[untyped-decorator]
def run_preview_job(job_id: str) -> None:
    """Load and conditionally execute one durable UUID-bound attempt."""
    try:
        durable_job_id = UUID(job_id)
    except TypeError, ValueError:
        return
    execute_preview_job(
        SessionFactory,
        job_id=durable_job_id,
        processor=_bounded_processor,
    )
