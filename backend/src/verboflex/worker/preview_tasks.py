"""UUID-only Celery execution for durable commit-bound preview attempts."""

import asyncio
from collections.abc import Mapping
from uuid import UUID

from billiard.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.core.config import get_settings
from verboflex.db.session import SessionFactory
from verboflex.integrations.readers import create_repository_read_adapters
from verboflex.localization.duplicate_diagnostics import inspect_duplicate_keys
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.moko_layout import moko_layout
from verboflex.localization.preview.registry import detect_preview_layouts
from verboflex.models.preview_job import PreviewJob
from verboflex.services.duplicate_reports import store_report
from verboflex.services.preview_jobs import (
    PreviewJobIdentity,
    PreviewJobTimedOut,
    PreviewProcessor,
    _current_failure_code,
    _matches_started_identity,
    execute_preview_job,
    reconcile_stale_preview_jobs,
)
from verboflex.services.repository_discovery import (
    ReadAdapters,
    discover_live_repository_sources,
)
from verboflex.worker.celery_app import app


async def _process_preview(
    identity: PreviewJobIdentity,
    *,
    factory: sessionmaker[Session],
    adapter: ReadAdapters,
) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    diagnostic_inputs: list[CanonicalParserInput] = []
    diagnostic_sources: list[dict[str, str]] = []
    for side in identity.repository_sides:
        with factory() as session:
            snapshot = await discover_live_repository_sources(
                session,
                repository_id=side.repository_id,
                branch=side.source_branch,
                adapter=adapter,
                localization_root=side.localization_root,
            )
        if snapshot.commit_hash != side.commit_hash:
            raise ValueError("preview commit changed during discovery")
        diagnostic_sources.append(
            dict(
                repository_side=side.role,
                repository_id=str(side.repository_id),
                source_branch=side.source_branch,
                commit_hash=side.commit_hash,
            )
        )
        for file in snapshot.files:
            layout = moko_layout(file.path)
            if layout is not None:
                diagnostic_inputs.append(
                    CanonicalParserInput(
                        format="android_xml",
                        repository_side=side.role,
                        path=file.path,
                        content=file.content,
                        layout_identity=layout[0],
                        layout_version=1,
                        base_language="und",
                    )
                )
        candidates.extend(
            detect_preview_layouts(
                snapshot.files,
                repository_side=side.role,
            ).to_mappings()
        )
    if diagnostic_inputs:
        report = inspect_duplicate_keys(tuple(diagnostic_inputs))
        if not report.complete:
            # Complete duplicate identities are quarantined by the preview
            # parser; incomplete diagnostics still fail closed.
            candidates.clear()
        with factory.begin() as session:
            owner = session.scalar(
                select(PreviewJob).where(PreviewJob.id == identity.job_id).with_for_update()
            )
            if (
                owner is not None
                and owner.state == "running"
                and _matches_started_identity(owner, identity)
                and _current_failure_code(session, owner, for_update=True) is None
            ):
                store_report(
                    session,
                    report=report,
                    sources=diagnostic_sources,
                    preview_job_id=identity.job_id,
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
    adapter: ReadAdapters,
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
    adapter: ReadAdapters,
) -> Mapping[str, object]:
    """Retain the Plan 12 call seam while delegating to the complete registry."""
    return process_preview(identity, factory=factory, adapter=adapter)


async def _production_preview(identity: PreviewJobIdentity) -> dict[str, object]:
    settings = get_settings()
    adapter = create_repository_read_adapters(settings)
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
_preview_task_settings = get_settings()


def _bounded_processor(identity: PreviewJobIdentity) -> dict[str, object]:
    try:
        return dict(preview_processor(identity))
    except SoftTimeLimitExceeded as error:
        raise PreviewJobTimedOut from error


@app.task(
    name="verboflex.preview.run",
    soft_time_limit=_preview_task_settings.preview_soft_time_limit_seconds,
    time_limit=_preview_task_settings.preview_hard_time_limit_seconds,
    acks_late=True,
    reject_on_worker_lost=True,
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


@app.task(
    name="verboflex.preview.reconcile_stale_jobs",
    serializer="json",
    ignore_result=True,
)  # type: ignore[untyped-decorator]
def reconcile_stale_jobs() -> int:
    """Run one bounded, idempotent stale-attempt recovery batch."""
    settings = get_settings()
    return reconcile_stale_preview_jobs(
        SessionFactory,
        hard_time_limit_seconds=settings.preview_hard_time_limit_seconds,
        watchdog_grace_seconds=settings.preview_watchdog_grace_seconds,
    )
