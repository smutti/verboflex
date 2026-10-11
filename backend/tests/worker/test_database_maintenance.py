"""The daily worker uses the same bounded policy and PostgreSQL service as the CLI."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from tests.integration.test_database_maintenance import (  # noqa: F401
    maintenance_factory,
    seed_staging,
)
from verboflex.core.config import Settings
from verboflex.services import database_maintenance as maintenance
from verboflex.worker import database_maintenance_tasks as tasks
from verboflex.worker.celery_app import create_celery_app


def test_daily_schedule_and_defaults():
    settings = Settings()
    assert settings.maintenance_temporary_retention_days == 7
    assert settings.maintenance_deleted_product_retention_days is None
    app = create_celery_app(settings)
    entry = app.conf.beat_schedule["database-daily-maintenance"]
    assert entry["task"] == "verboflex.maintenance.run"
    assert entry["schedule"].hour == {3} and entry["schedule"].minute == {30}
    assert "verboflex.worker.database_maintenance_tasks" in app.conf.include
    assert app.conf.task_annotations["verboflex.maintenance.run"]["soft_time_limit"] == 55
    assert app.conf.task_annotations["verboflex.maintenance.run"]["time_limit"] == 65


@pytest.mark.parametrize(
    "values",
    [
        {"maintenance_batch_rows": 0},
        {"maintenance_deleted_product_retention_days": 0},
        {"maintenance_max_rows_per_run": 10, "maintenance_batch_rows": 11},
        {"maintenance_max_run_seconds": 1, "maintenance_statement_timeout_ms": 5000},
        {"maintenance_lock_timeout_ms": 1001, "maintenance_statement_timeout_ms": 1000},
    ],
)
def test_invalid_settings(values):
    with pytest.raises(ValidationError):
        Settings(**values)


def test_worker_real_database_and_safe_payload(maintenance_factory, monkeypatch):  # noqa: F811
    seed_staging(maintenance_factory)
    future = datetime.now(UTC) + timedelta(days=8)

    class Clock:
        @staticmethod
        def now(zone):
            return future

    monkeypatch.setattr(tasks, "datetime", Clock)
    monkeypatch.setattr(tasks, "SessionFactory", maintenance_factory)
    monkeypatch.setattr(tasks, "get_settings", lambda: Settings())
    result = tasks.run_database_maintenance.run()
    assert result["status"] == "complete" and result["deleted_rows"] == 2
    assert tasks.run_database_maintenance.run()["deleted_rows"] == 0
    with pytest.raises(TypeError):
        tasks.run_database_maintenance.run(product_id="untrusted")


def test_scheduled_resume_reuses_digest_and_default_never_purges(maintenance_factory):  # noqa: F811
    from tests.integration.test_database_maintenance import mark_deleted
    from verboflex.models.product import Product

    factory = maintenance_factory
    identity = seed_staging(factory)
    mark_deleted(factory, identity.product_id)
    now = datetime.now(UTC) + timedelta(days=8)
    policy = maintenance.MaintenancePolicy(batch_rows=1, max_rows_per_run=1)
    first = maintenance.run_scheduled_maintenance(factory, policy, now)
    assert first.deleted_rows == 1 and first.status == "partial"
    second = maintenance.run_scheduled_maintenance(factory, policy, now + timedelta(minutes=1))
    assert second.digest == first.digest
    assert second.deleted_rows == 1 and second.status == "complete"
    with factory() as session:
        assert session.get(Product, identity.product_id) is not None
        manual = maintenance.build_manifest(
            session, policy, [identity.product_id], now, temporary=False
        )
        assert manual.targets[0].kind == "product"
        automatic = maintenance.build_manifest(
            session,
            maintenance.MaintenancePolicy(deleted_product_retention_days=30),
            [],
            now,
            scheduled=True,
            temporary=False,
        )
        assert all(target.id != identity.product_id for target in automatic.targets)
        automatic = maintenance.build_manifest(
            session,
            maintenance.MaintenancePolicy(deleted_product_retention_days=30),
            [],
            now + timedelta(days=31),
            scheduled=True,
            temporary=False,
        )
        assert any(target.id == identity.product_id for target in automatic.targets)


def test_task_retry_budget_and_mocked_broker_dispatch(monkeypatch):
    from unittest.mock import Mock

    from sqlalchemy.exc import OperationalError

    def unavailable(*args):
        raise OperationalError("private SQL", {}, RuntimeError("private failure"))

    retry = Mock(side_effect=RuntimeError("retry captured"))
    monkeypatch.setattr(tasks, "run_scheduled_maintenance", unavailable)
    monkeypatch.setattr(tasks.run_database_maintenance, "retry", retry)
    with pytest.raises(RuntimeError, match="retry captured"):
        tasks.run_database_maintenance.run()
    assert retry.call_args.kwargs["max_retries"] == 3
    assert str(retry.call_args.kwargs["exc"]) == "maintenance database unavailable"
    dispatch = Mock()
    monkeypatch.setattr(tasks.run_database_maintenance, "apply_async", dispatch)
    tasks.run_database_maintenance.delay()
    dispatch.assert_called_once_with((), {})
