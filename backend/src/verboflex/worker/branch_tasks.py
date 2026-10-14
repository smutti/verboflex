"""Durable approval outbox dispatcher and serial branch worker."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select

from verboflex.core.config import get_settings
from verboflex.db.session import SessionFactory
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.integrations.bitbucket.writes import BitbucketWriteAdapter
from verboflex.models.branch_workflow import BranchJob
from verboflex.services.bitbucket_oauth import BitbucketOAuthService, BitbucketOAuthTokenExchange
from verboflex.services.branch_jobs import LEASE, execute_branch_job, refresh_branch_pr
from verboflex.worker.celery_app import app


async def _run(job_id: UUID) -> None:
    settings = get_settings()
    reads = BitbucketHttpAdapter(
        settings=settings,
        credential_leases=BitbucketOAuthService(
            settings=settings, token_exchange=BitbucketOAuthTokenExchange()
        ),
    )
    try:
        with SessionFactory() as s:
            row = s.get(BranchJob, job_id)
            refresh = row is not None and row.state == "open"
        if refresh:
            await refresh_branch_pr(
                SessionFactory, job_id=job_id, writes=BitbucketWriteAdapter(reads=reads)
            )
        else:
            await execute_branch_job(
                SessionFactory,
                job_id=job_id,
                reads=reads,
                writes=BitbucketWriteAdapter(reads=reads),
            )
    finally:
        await reads.aclose()


@app.task(
    name="verboflex.branch.run", acks_late=True, reject_on_worker_lost=True, ignore_result=True
)  # type: ignore[untyped-decorator]
def run_branch_job(job_id: str) -> None:
    try:
        value = UUID(job_id)
    except ValueError, TypeError:
        return
    asyncio.run(_run(value))


@app.task(name="verboflex.branch.dispatch", ignore_result=True)  # type: ignore[untyped-decorator]
def dispatch_branch_jobs() -> int:
    now = datetime.now(UTC)
    with SessionFactory() as s:
        ids = list(
            s.scalars(
                select(BranchJob.id)
                .where(
                    or_(
                        BranchJob.state == "queued",
                        (BranchJob.state.in_(("running", "sending")))
                        & (BranchJob.updated_at < now - LEASE),
                        (BranchJob.state == "open")
                        & (BranchJob.updated_at < now - timedelta(minutes=1)),
                    )
                )
                .order_by(BranchJob.sequence)
                .limit(100)
            )
        )
    for job_id in ids:
        run_branch_job.delay(str(job_id))
    return len(ids)
