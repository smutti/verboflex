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
    ImportProcessingResult,
    ImportProcessor,
    _process_import,
    classify_import_movement,
    execute_import_job,
    reconcile_stale_imports,
)
from verboflex.services.import_jobs import (
    process_import as process_import,
)
from verboflex.services.repository_discovery import SourceDiscoveryAdapter
from verboflex.worker.celery_app import app


async def _production_import(
    identity: ImportExecutionIdentity,
) -> ImportProcessingResult:
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
        processed = await _process_import_with_adapter(
            identity,
            factory=SessionFactory,
            adapter=adapter,
        )
        movement = await classify_import_movement(
            identity,
            references=processed.references,
            factory=SessionFactory,
            adapter=adapter,
        )
        return ImportProcessingResult(
            references=processed.references,
            movement=movement,
            canonical_manifest_digest=processed.canonical_manifest_digest,
        )
    finally:
        await adapter.aclose()


async def _process_import_with_adapter(
    identity: ImportExecutionIdentity,
    *,
    factory: sessionmaker[Session],
    adapter: SourceDiscoveryAdapter,
) -> ImportProcessingResult:
    return await _process_import(
        identity,
        factory=factory,
        adapter=adapter,
    )


def production_import_processor(
    identity: ImportExecutionIdentity,
) -> ImportProcessingResult:
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
    soft_time_limit=_import_task_settings.import_soft_time_limit_seconds,
    time_limit=_import_task_settings.import_hard_time_limit_seconds,
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


@app.task(
    name="verboflex.import.reconcile_stale_jobs",
    serializer="json",
    ignore_result=True,
)  # type: ignore[untyped-decorator]
def reconcile_stale_import_jobs() -> int:
    """Terminalize one bounded batch of interrupted imports without redispatch."""
    settings = get_settings()
    return reconcile_stale_imports(
        SessionFactory,
        hard_time_limit_seconds=settings.import_hard_time_limit_seconds,
        watchdog_grace_seconds=settings.import_watchdog_grace_seconds,
    )
