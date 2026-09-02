"""UUID-only Celery execution for published-mapping imports."""

import asyncio
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from verboflex.core.config import get_settings
from verboflex.db.session import SessionFactory
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.services.bitbucket_oauth import (
    BitbucketOAuthService,
    BitbucketOAuthTokenExchange,
)
from verboflex.services.import_jobs import (
    ImportExecutionIdentity,
    ImportProcessor,
    ImportSourceReferenceRecord,
    _process_import,
    execute_import_job,
)
from verboflex.services.import_jobs import (
    process_import as process_import,
)
from verboflex.services.repository_discovery import SourceDiscoveryAdapter
from verboflex.worker.celery_app import app


async def _production_import(
    identity: ImportExecutionIdentity,
) -> tuple[ImportSourceReferenceRecord, ...]:
    settings = get_settings()
    oauth_service = BitbucketOAuthService(
        settings=settings,
        token_exchange=BitbucketOAuthTokenExchange(),
    )
    adapter = BitbucketHttpAdapter(
        settings=settings,
        credential_leases=oauth_service,
    )
    try:
        return await _process_import_with_adapter(
            identity,
            factory=SessionFactory,
            adapter=adapter,
        )
    finally:
        await adapter.aclose()


async def _process_import_with_adapter(
    identity: ImportExecutionIdentity,
    *,
    factory: sessionmaker[Session],
    adapter: SourceDiscoveryAdapter,
) -> tuple[ImportSourceReferenceRecord, ...]:
    return await _process_import(
        identity,
        factory=factory,
        adapter=adapter,
    )


def production_import_processor(
    identity: ImportExecutionIdentity,
) -> tuple[ImportSourceReferenceRecord, ...]:
    """Own and close one provider adapter for an exact durable execution."""
    return asyncio.run(_production_import(identity))


import_processor: ImportProcessor = production_import_processor
_import_task_settings = get_settings()


def enqueue_import_job(import_id: UUID) -> None:
    """Compatibility export for the UUID-only service enqueuer."""
    from verboflex.services.import_jobs import enqueue_import_job as enqueue

    enqueue(import_id)


@app.task(
    name="verboflex.import.run",
    soft_time_limit=_import_task_settings.preview_soft_time_limit_seconds,
    time_limit=_import_task_settings.preview_hard_time_limit_seconds,
    acks_late=True,
    reject_on_worker_lost=True,
    serializer="json",
    ignore_result=True,
)  # type: ignore[untyped-decorator]
def run_import_job(import_id: str) -> None:
    """Load and conditionally execute one stable logical import UUID."""
    try:
        durable_import_id = UUID(import_id)
    except TypeError, ValueError:
        return
    execute_import_job(
        SessionFactory,
        import_id=durable_import_id,
        processor=import_processor,
    )
