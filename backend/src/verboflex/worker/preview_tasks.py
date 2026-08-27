"""UUID-only Celery execution for durable commit-bound preview attempts."""

import asyncio
from collections.abc import Mapping
from uuid import UUID

from billiard.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from sqlalchemy.orm import Session, sessionmaker

from verboflex.auth.rate_limits import get_redis_client
from verboflex.core.config import get_settings
from verboflex.db.session import SessionFactory
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.localization.preview.registry import detect_preview_layouts
from verboflex.services.bitbucket_oauth import (
    BitbucketOAuthService,
    BitbucketOAuthTokenExchange,
)
from verboflex.services.preview_jobs import (
    PREVIEW_HARD_TIME_LIMIT_SECONDS,
    PREVIEW_SOFT_TIME_LIMIT_SECONDS,
    PreviewJobIdentity,
    PreviewJobTimedOut,
    PreviewProcessor,
    execute_preview_job,
)
from verboflex.services.repository_discovery import (
    SourceDiscoveryAdapter,
    discover_live_repository_sources,
)
from verboflex.worker.celery_app import app


async def _process_preview(
    identity: PreviewJobIdentity,
    *,
    factory: sessionmaker[Session],
    adapter: SourceDiscoveryAdapter,
) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    for side in identity.repository_sides:
        with factory() as session:
            snapshot = await discover_live_repository_sources(
                session,
                repository_id=side.repository_id,
                branch=side.source_branch,
                adapter=adapter,
            )
        if snapshot.commit_hash != side.commit_hash:
            raise ValueError("preview commit changed during discovery")
        candidates.extend(
            detect_preview_layouts(
                snapshot.files,
                repository_side=side.role,
            ).to_mappings()
        )
    candidates.sort(
        key=lambda candidate: (
            str(candidate["repository_side"]),
            str(candidate["format"]),
            str(candidate["layout_identity"]),
            str(candidate["id"]),
        )
    )
    return {
        "detector_version": identity.detector_version,
        "digest": identity.input_digest,
        "layout_candidates": candidates,
    }


def process_preview(
    identity: PreviewJobIdentity,
    *,
    factory: sessionmaker[Session],
    adapter: SourceDiscoveryAdapter,
) -> Mapping[str, object]:
    """Resolve exact commits and detect every strict read-only preview format."""
    return asyncio.run(
        _process_preview(
            identity,
            factory=factory,
            adapter=adapter,
        )
    )


def process_android_preview(
    identity: PreviewJobIdentity,
    *,
    factory: sessionmaker[Session],
    adapter: SourceDiscoveryAdapter,
) -> Mapping[str, object]:
    """Retain the Plan 12 call seam while delegating to the complete registry."""
    return process_preview(identity, factory=factory, adapter=adapter)


async def _production_preview(identity: PreviewJobIdentity) -> dict[str, object]:
    settings = get_settings()
    oauth_service = BitbucketOAuthService(
        settings=settings,
        redis_client=get_redis_client(settings),
        token_exchange=BitbucketOAuthTokenExchange(),
    )
    adapter = BitbucketHttpAdapter(
        settings=settings,
        credential_leases=oauth_service,
    )
    try:
        return await _process_preview(
            identity,
            factory=SessionFactory,
            adapter=adapter,
        )
    finally:
        await adapter.aclose()


def production_preview_processor(identity: PreviewJobIdentity) -> Mapping[str, object]:
    """Own one bounded provider client for a durable worker execution."""
    return asyncio.run(_production_preview(identity))


preview_processor: PreviewProcessor = production_preview_processor


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
