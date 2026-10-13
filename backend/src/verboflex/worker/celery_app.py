"""Celery application configured for the separate Redis-backed worker process."""

from celery import Celery  # type: ignore[import-untyped]
from celery.schedules import crontab  # type: ignore[import-untyped]

from verboflex.core.config import Settings, get_settings
from verboflex.schemas.system import ServiceState

PREVIEW_RUN_TASK_NAME = "verboflex.preview.run"
PREVIEW_RECONCILE_TASK_NAME = "verboflex.preview.reconcile_stale_jobs"
IMPORT_RUN_TASK_NAME = "verboflex.import.run"
IMPORT_RECONCILE_TASK_NAME = "verboflex.import.reconcile_stale_jobs"


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Create one JSON-only worker application from typed settings."""
    configured = settings or get_settings()
    redis_url = str(configured.redis_url)
    application = Celery(
        "verboflex",
        broker=redis_url,
        backend=redis_url,
        include=[
            "verboflex.worker.tasks",
            "verboflex.worker.screenshot_tasks",
            "verboflex.worker.preview_tasks",
            "verboflex.worker.import_tasks",
            "verboflex.worker.submission_tasks",
            "verboflex.worker.database_maintenance_tasks",
            "verboflex.worker.mcp_oauth_tasks",
        ],
    )
    application.conf.update(
        accept_content=["json"],
        result_accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        task_always_eager=False,
        task_ignore_result=False,
        task_track_started=True,
        enable_utc=True,
        timezone="UTC",
        broker_connection_retry_on_startup=True,
        broker_connection_timeout=configured.service_probe_timeout_seconds,
        redis_socket_connect_timeout=configured.service_probe_timeout_seconds,
        redis_socket_timeout=configured.service_probe_timeout_seconds,
        result_backend_max_retries=1,
        result_expires=300,
        worker_hijack_root_logger=False,
        task_routes={"verboflex.screenshot.run": {"queue": "screenshots"}},
        task_annotations={
            "verboflex.screenshot.run": {
                "soft_time_limit": configured.screenshot_timeout_seconds + 30,
                "time_limit": configured.screenshot_timeout_seconds + 60,
            },
            "verboflex.maintenance.run": {
                "acks_late": True,
                "reject_on_worker_lost": True,
                "soft_time_limit": configured.maintenance_max_run_seconds + 10,
                "time_limit": configured.maintenance_max_run_seconds + 20,
            },
            "verboflex.submission.reconcile": {
                "acks_late": True,
                "reject_on_worker_lost": True,
                "soft_time_limit": configured.import_soft_time_limit_seconds,
                "time_limit": configured.import_hard_time_limit_seconds,
            },
            "verboflex.submission.dispatch_pending": {
                "soft_time_limit": configured.import_soft_time_limit_seconds,
                "time_limit": configured.import_hard_time_limit_seconds,
            },
            "verboflex.submission.run": {
                "acks_late": True,
                "reject_on_worker_lost": True,
                "soft_time_limit": configured.import_soft_time_limit_seconds,
                "time_limit": configured.import_hard_time_limit_seconds,
            },
            "verboflex.submission_review.run": {
                "acks_late": True,
                "reject_on_worker_lost": True,
                "soft_time_limit": configured.import_soft_time_limit_seconds,
                "time_limit": configured.import_hard_time_limit_seconds,
            },
            PREVIEW_RUN_TASK_NAME: {
                "acks_late": True,
                "reject_on_worker_lost": True,
                "soft_time_limit": configured.preview_soft_time_limit_seconds,
                "time_limit": configured.preview_hard_time_limit_seconds,
            },
            IMPORT_RUN_TASK_NAME: {
                "acks_late": True,
                "reject_on_worker_lost": True,
                "soft_time_limit": configured.import_soft_time_limit_seconds,
                "time_limit": configured.import_hard_time_limit_seconds,
            },
        },
        beat_schedule={
            "screenshot-durable-dispatch": {
                "task": "verboflex.screenshot.reconcile",
                "schedule": 10.0,
            },
            "mcp-oauth-hourly-cleanup": {
                "task": "verboflex.mcp.cleanup",
                "schedule": crontab(minute=15),
            },
            "database-daily-maintenance": {
                "task": "verboflex.maintenance.run",
                "schedule": crontab(hour=3, minute=30),
            },
            "submission-durable-dispatch": {
                "task": "verboflex.submission.dispatch_pending",
                "schedule": float(configured.import_watchdog_interval_seconds),
            },
            "preview-stale-job-watchdog": {
                "task": PREVIEW_RECONCILE_TASK_NAME,
                "schedule": float(configured.preview_watchdog_interval_seconds),
            },
            "import-stale-execution-watchdog": {
                "task": IMPORT_RECONCILE_TASK_NAME,
                "schedule": float(configured.import_watchdog_interval_seconds),
            },
        },
        beat_max_loop_interval=min(
            configured.preview_watchdog_interval_seconds,
            configured.import_watchdog_interval_seconds,
        ),
    )
    return application


def probe_worker_state(
    application: Celery,
    *,
    timeout_seconds: float,
) -> ServiceState:
    """Project a bounded Celery control ping onto the public safe state enum."""
    try:
        replies = application.control.inspect(timeout=timeout_seconds).ping()
    except Exception:
        return "unavailable"
    return "online" if replies else "unavailable"


app = create_celery_app()
