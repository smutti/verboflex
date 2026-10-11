"""UUID-only review/submission jobs; own and close their provider connection pool."""

import asyncio
from uuid import UUID

from verboflex.core.config import get_settings
from verboflex.db.session import SessionFactory
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.integrations.bitbucket.writes import BitbucketWriteAdapter
from verboflex.services.bitbucket_oauth import BitbucketOAuthService, BitbucketOAuthTokenExchange
from verboflex.services.submission_jobs import execute_change_set, recover_change_set
from verboflex.services.submission_reviews import execute_submission_review
from verboflex.worker.celery_app import app


async def _execute(review_id: UUID) -> None:
    settings = get_settings()
    adapter = BitbucketHttpAdapter(
        settings=settings,
        credential_leases=BitbucketOAuthService(
            settings=settings, token_exchange=BitbucketOAuthTokenExchange()
        ),
    )
    try:
        await execute_submission_review(SessionFactory, review_id=review_id, adapter=adapter)
    finally:
        await adapter.aclose()


@app.task(
    name="verboflex.submission_review.run",
    acks_late=True,
    reject_on_worker_lost=True,
    serializer="json",
    ignore_result=True,
)  # type: ignore[untyped-decorator]
def run_submission_review(review_id: str) -> None:
    try:
        value = UUID(review_id)
    except TypeError, ValueError:
        return
    asyncio.run(_execute(value))


async def _submit(change_set_id: UUID, *, reconcile: bool = False) -> None:
    settings = get_settings()
    adapter = BitbucketHttpAdapter(
        settings=settings,
        credential_leases=BitbucketOAuthService(
            settings=settings, token_exchange=BitbucketOAuthTokenExchange()
        ),
    )
    try:
        operation = recover_change_set if reconcile else execute_change_set
        await operation(
            SessionFactory,
            change_set_id=change_set_id,
            reads=adapter,
            writes=BitbucketWriteAdapter(reads=adapter),
        )
    finally:
        await adapter.aclose()


@app.task(
    name="verboflex.submission.run",
    acks_late=True,
    reject_on_worker_lost=True,
    serializer="json",
    ignore_result=True,
)  # type: ignore[untyped-decorator]
def run_submission(change_set_id: str) -> None:
    if not isinstance(change_set_id, str):
        return
    try:
        value = UUID(change_set_id)
    except TypeError, ValueError:
        return
    asyncio.run(_submit(value))


@app.task(
    name="verboflex.submission.reconcile",
    acks_late=True,
    reject_on_worker_lost=True,
    serializer="json",
    ignore_result=True,
)  # type: ignore[untyped-decorator]
def run_submission_reconciliation(change_set_id: str) -> None:
    if not isinstance(change_set_id, str):
        return
    try:
        value = UUID(change_set_id)
    except TypeError, ValueError:
        return
    asyncio.run(_submit(value, reconcile=True))


@app.task(
    name="verboflex.submission.dispatch_pending",
    serializer="json",
    ignore_result=True,
)  # type: ignore[untyped-decorator]
def dispatch_pending_submissions() -> int:
    from verboflex.services.submission_dispatch import dispatch_pending_submissions as dispatch
    from verboflex.services.submission_recovery import enqueue_reconciliation
    from verboflex.services.submissions import enqueue_submission

    return dispatch(
        SessionFactory, enqueue_send=enqueue_submission, enqueue_reconcile=enqueue_reconciliation
    )
