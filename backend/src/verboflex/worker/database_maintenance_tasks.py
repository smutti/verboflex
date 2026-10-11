"""Payload-free scheduled upkeep: no provider calls or externally selected database targets."""

import logging
from datetime import UTC, datetime

from billiard.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from sqlalchemy.exc import DBAPIError

from verboflex.core.config import get_settings
from verboflex.db.session import SessionFactory
from verboflex.services.database_maintenance import MaintenancePolicy, run_scheduled_maintenance
from verboflex.worker.celery_app import app

logger = logging.getLogger(__name__)


class MaintenanceTransientError(RuntimeError):
    """Sanitized retry signal: database exceptions never enter task results/logs."""


@app.task(
    name="verboflex.maintenance.run",
    acks_late=True,
    reject_on_worker_lost=True,
    serializer="json",
    autoretry_for=(MaintenanceTransientError,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=10,
    retry_backoff_max=120,
    retry_jitter=True,
)  # type: ignore[untyped-decorator]
def run_database_maintenance() -> dict[str, object]:
    policy = MaintenancePolicy.from_settings(get_settings())
    try:
        result = run_scheduled_maintenance(SessionFactory, policy, datetime.now(UTC))
    except SoftTimeLimitExceeded:
        return {"status": "partial", "reason": "time_budget"}
    except DBAPIError:
        raise MaintenanceTransientError("maintenance database unavailable") from None
    if result.reason == "database_busy_or_error":
        raise MaintenanceTransientError("maintenance database busy")
    logger.info(
        "database maintenance status=%s deleted_rows=%d remaining_rows=%d",
        result.status,
        result.deleted_rows,
        result.remaining_rows,
    )
    return result.model_dump(mode="json")
