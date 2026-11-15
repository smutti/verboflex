"""Database outbox linking verified commits to normal, permission-checked imports."""

import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.models.branch_workflow import BranchJob, BranchWorkflow
from verboflex.models.import_job import ImportExecution, ImportJob
from verboflex.services import import_jobs
from verboflex.services.branch_workflow import active_mapping
from verboflex.services.translation_authoring import AuthoringError, _product

logger = logging.getLogger(__name__)


def refresh_committed_catalogs(
    factory: sessionmaker[Session],
    *,
    enqueuer: Callable[[UUID], None] = import_jobs.enqueue_import_job,
) -> int:
    """Coalesce a branch batch. Repeated/crashed dispatch never repeats a commit."""
    with factory() as session:
        workflows = list(
            session.scalars(
                select(BranchJob.workflow_id)
                .where(
                    BranchJob.state == "committed",
                    BranchJob.catalog_refresh_state.in_(("pending", "running")),
                )
                .distinct()
                .limit(100)
            )
        )
    dispatched: set[UUID] = set()
    for workflow_id in workflows:
        try:
            with factory.begin() as session:
                jobs = list(
                    session.scalars(
                        select(BranchJob)
                        .where(
                            BranchJob.workflow_id == workflow_id,
                            BranchJob.state == "committed",
                            BranchJob.catalog_refresh_state.in_(("pending", "running")),
                        )
                        .order_by(BranchJob.sequence)
                        .with_for_update(skip_locked=True)
                    )
                )
                if not jobs:
                    continue
                workflow = session.get_one(BranchWorkflow, workflow_id)
                mapping = active_mapping(session, workflow)
                pending = [job for job in jobs if job.catalog_refresh_state == "pending"]
                for job in jobs:
                    if job.catalog_refresh_state != "running":
                        continue
                    execution = session.get(ImportExecution, job.catalog_refresh_execution_id)
                    if execution is None or execution.state == "failed":
                        job.catalog_refresh_state = "failed"
                    elif execution.state == "succeeded":
                        job.catalog_refresh_state = "succeeded"
                    elif execution.state == "queued":
                        # Also repairs a broker failure after the transaction committed.
                        dispatched.add(execution.import_job_id)
                if not pending:
                    continue
                try:
                    _product(session, workflow.product_id, pending[-1].actor_id, "read", lock=False)
                except AuthoringError:
                    for job in pending:
                        job.catalog_refresh_state = "failed"
                    continue
                if mapping is None or not any(
                    side.repository_id == workflow.repository_id
                    and side.source_branch == workflow.work_branch
                    and side.role in ("direct", "translations")
                    for side in mapping.sides
                ):
                    # Never change a configured source branch or base language.
                    for job in pending:
                        job.catalog_refresh_state = "skipped"
                    continue
                if session.scalar(
                    select(BranchJob.id)
                    .where(
                        BranchJob.workflow_id == workflow_id,
                        BranchJob.state.in_(("queued", "running", "sending")),
                    )
                    .limit(1)
                ):
                    continue
                current = session.scalar(
                    select(ImportJob).where(ImportJob.mapping_id == mapping.id)
                )
                if current is not None and current.state in ("queued", "running"):
                    # An older execution might have frozen the head before our commit.
                    # Wait for it; do not claim that it contains our changes.
                    continue
                try:
                    with session.begin_nested():
                        record = import_jobs.queue_import_in_transaction(
                            session,
                            actor_id=pending[-1].actor_id,
                            product_id=workflow.product_id,
                            mapping_id=mapping.id,
                        )
                        assert record.id is not None
                        current = session.get_one(ImportJob, record.id)
                        for job in pending:
                            job.catalog_refresh_state = "running"
                            job.catalog_refresh_execution_id = current.current_execution_id
                        dispatched.add(record.id)
                except import_jobs.ImportAlreadyInProgress:
                    continue
                except ValueError, RuntimeError:
                    # Normal import guards (review/revalidation/revocation) still apply.
                    for job in pending:
                        job.catalog_refresh_state = "failed"
                    logger.warning(
                        "Catalog refresh requires attention for workflow %s", workflow_id
                    )
        except Exception:
            logger.exception("Could not queue catalog refresh for workflow %s", workflow_id)
    for import_id in dispatched:
        try:
            enqueuer(import_id)
        except Exception:
            logger.warning("Catalog refresh dispatch will retry for import %s", import_id)
    return len(dispatched)
