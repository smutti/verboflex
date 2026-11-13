"""Durable draft approval dispatcher: no dependency on an open browser."""

from uuid import UUID

from sqlalchemy import select

from verboflex.db.session import SessionFactory
from verboflex.models.authoring_approval import AuthoringApproval
from verboflex.services.authoring_approvals import execute
from verboflex.worker.celery_app import app


@app.task(
    name="verboflex.authoring.approve",
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
    soft_time_limit=900,
    time_limit=960,
)  # type: ignore[untyped-decorator]
def approve_drafts(job_id: str) -> None:
    try:
        value = UUID(job_id)
    except ValueError, TypeError:
        return
    execute(SessionFactory, job_id=value)


@app.task(name="verboflex.authoring.dispatch", ignore_result=True)  # type: ignore[untyped-decorator]
def dispatch_approvals() -> int:
    with SessionFactory() as session:
        ids = list(
            session.scalars(
                select(AuthoringApproval.id)
                .where(
                    AuthoringApproval.state == "queued",
                )
                .order_by(AuthoringApproval.created_at)
                .limit(100)
            )
        )
    for job_id in ids:
        approve_drafts.delay(str(job_id))
    return len(ids)
