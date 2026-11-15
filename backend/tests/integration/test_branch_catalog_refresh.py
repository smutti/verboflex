"""Verified commits refresh through a coalesced, durable database outbox."""

import pytest
from sqlalchemy import func, select

from tests.integration.test_branch_workflow import approve, run, setup
from tests.integration.test_preview_jobs import clean_preview_database as clean_preview_database
from tests.integration.test_preview_jobs import preview_session_factory as preview_session_factory
from verboflex.models.branch_workflow import BranchJob
from verboflex.models.import_job import ImportExecution, ImportJob
from verboflex.models.translation import LocalizationScope, TranslationValue
from verboflex.models.user import User
from verboflex.services.branch_catalog_refresh import refresh_committed_catalogs


def test_coalesced_refresh_survives_broker_failure(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch, work_branch="main", target_branch="release")
    jobs = []
    for text in ("First text", "Second text"):
        job_id = approve(factory, seed, text)
        assert run(factory, remote, job_id)[0] == "committed"
        jobs.append(job_id)
    with factory() as session:
        before = session.scalar(select(func.count()).select_from(ImportExecution))

    def offline(_):
        raise ConnectionError("synthetic broker outage")

    refresh_committed_catalogs(factory, enqueuer=offline)
    with factory() as session:
        rows = [session.get_one(BranchJob, identity) for identity in jobs]
        assert {row.catalog_refresh_state for row in rows} == {"running"}
        assert len({row.catalog_refresh_execution_id for row in rows}) == 1
        execution_id = rows[0].catalog_refresh_execution_id
        import_id = session.get_one(ImportExecution, execution_id).import_job_id
        assert session.scalar(select(func.count()).select_from(ImportExecution)) == before + 1
    sent = []
    refresh_committed_catalogs(factory, enqueuer=sent.append)
    assert sent == [import_id]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ImportExecution)) == before + 1
    seed.adapter.files = dict(remote.versions[remote.head])
    seed.adapter.commit_hashes = [remote.head]
    from verboflex.worker.import_tasks import run_import_job

    run_import_job.run(str(import_id))
    refresh_committed_catalogs(factory, enqueuer=sent.append)
    with factory() as session:
        assert session.get_one(ImportExecution, execution_id).state == "succeeded", session.get_one(
            ImportJob, import_id
        ).error_category
        assert all(
            session.get_one(BranchJob, identity).catalog_refresh_state == "succeeded"
            for identity in jobs
        )
        assert session.scalar(
            select(LocalizationScope.active_execution_id).where(
                LocalizationScope.product_id == seed.product_id
            )
        ) == execution_id
        assert "Second text" in session.scalars(select(TranslationValue.display_text)).all()
    assert len(remote.commits) == 2 and remote.prs == []


@pytest.mark.parametrize("condition", ["branch_mismatch", "revoked", "import_failed", "busy"])
def test_refresh_guards(preview_session_factory, monkeypatch, condition):
    factory = preview_session_factory
    seed, remote = setup(
        factory,
        monkeypatch,
        work_branch="other" if condition == "branch_mismatch" else "main",
        target_branch="release",
    )
    job_id = approve(factory, seed, "Saved")
    assert run(factory, remote, job_id)[0] == "committed"
    if condition == "revoked":
        with factory.begin() as session:
            session.get_one(User, seed.actor_id).is_active = False
    if condition == "busy":
        approve(factory, seed, "Next save")
    sent = []
    refresh_committed_catalogs(factory, enqueuer=sent.append)
    with factory() as session:
        job = session.get_one(BranchJob, job_id)
        assert (
            job.catalog_refresh_state
            == {
                "branch_mismatch": "skipped",
                "revoked": "failed",
                "busy": "pending",
                "import_failed": "running",
            }[condition]
        )
        execution_id = job.catalog_refresh_execution_id
    if condition == "import_failed":
        from datetime import UTC, datetime

        with factory.begin() as session:
            execution = session.get_one(ImportExecution, execution_id)
            execution.state = "failed"
            execution.started_at = execution.finished_at = datetime.now(UTC)
            imported = session.get_one(ImportJob, execution.import_job_id)
            imported.state, imported.error_category, imported.error_message = (
                "import_failed",
                "provider_unavailable",
                "Synthetic error",
            )
        refresh_committed_catalogs(factory, enqueuer=sent.append)
        with factory() as session:
            assert session.get_one(BranchJob, job_id).catalog_refresh_state == "failed"
    else:
        assert sent == []
