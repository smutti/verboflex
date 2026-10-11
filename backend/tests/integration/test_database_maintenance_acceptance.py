"""Combined maintenance acceptance in a newly owned, fully migrated PostgreSQL DB."""

import importlib.util
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.api import test_translation_workspace as workspace
from tests.integration.test_database_maintenance import (
    BitbucketFileDelta,
    _json_result,
    _seed_running_direct_import,
    _stage_direct_manifest,
    _start_refresh_execution,
    import_jobs,
    maintenance_factory,  # noqa: F401
    mark_deleted,
    seed_staging,
)
from tests.integration.test_writeback_authority import _capture, seed_writeback_authority
from verboflex import cli
from verboflex.main import app
from verboflex.models.product import Product
from verboflex.services import database_maintenance as maintenance
from verboflex.worker import database_maintenance_tasks as worker

SPEC = importlib.util.spec_from_file_location(
    "maintenance_evidence",
    Path(__file__).resolve().parents[3] / "tools/verify_database_maintenance.py",
)
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


def seed_pending_rewrite(factory):
    first, repository = _seed_running_direct_import(factory)
    staged, references = _stage_direct_manifest(
        factory,
        identity=first,
        repository_id=repository,
        result=_json_result(),
        commit_hash="1" * 40,
    )
    assert import_jobs.finish_import_execution(
        factory, identity=first, references=references, canonical_manifest_digest=staged.digest
    )
    second = _start_refresh_execution(factory, first)
    staged, references = _stage_direct_manifest(
        factory,
        identity=second,
        repository_id=repository,
        result=_json_result(translated="Changed"),
        commit_hash="2" * 40,
    )
    sides = (
        import_jobs.SourceMovementSideComparison(
            repository_side="direct",
            repository_id=repository,
            active_commit_hash="1" * 40,
            proposed_commit_hash="2" * 40,
            relation="diverged",
        ),
    )
    assert import_jobs.finish_import_execution(
        factory,
        identity=second,
        references=references,
        movement=import_jobs.SourceMovementClassification(
            movement="review-required",
            sides=sides,
            rewrite_candidate=import_jobs.SourceRewriteCandidate(
                sides=sides,
                complete=True,
                files=(
                    BitbucketFileDelta(
                        repository_side="direct", ordinal=0, change="modified", path="locales.json"
                    ),
                ),
            ),
        ),
        canonical_manifest_digest=staged.digest,
    )
    return first, second


def test_foreign_cluster_identity_refuses_apply_and_snapshot(maintenance_factory):  # noqa: F811
    factory = maintenance_factory
    staged = seed_staging(factory)
    policy = maintenance.MaintenancePolicy()
    now = datetime.now(UTC) + timedelta(days=8)
    with factory() as session:
        manifest = maintenance.build_manifest(session, policy, [], now)
        cluster, name, oid = session.execute(
            text(
                "SELECT system_identifier::text, current_database(), oid::text "
                "FROM pg_database CROSS JOIN pg_catalog.pg_control_system() "
                "WHERE datname=current_database()"
            )
        ).one()
        assert manifest.database_identity == maintenance._digest((cluster, name, oid))
        foreign = manifest.model_copy(
            update={"database_identity": maintenance._digest((str(int(cluster) + 1), name, oid))}
        )
        foreign = foreign.model_copy(update={"digest": foreign.calculated_digest()})
        before_runs = session.scalar(text("SELECT count(*) FROM maintenance_runs"))
        before_batches = session.scalar(text("SELECT count(*) FROM maintenance_batches"))
    with pytest.raises(ValueError, match="database_or_schema_mismatch"):
        maintenance.apply_manifest(factory, foreign, policy, now)
    with pytest.raises(ValueError, match="manifest identity mismatch"):
        evidence.snapshot(factory, foreign)
    with factory() as session:
        assert maintenance._staging_count(session, staged.execution_id) == 2
        assert session.scalar(text("SELECT count(*) FROM maintenance_runs")) == before_runs
        assert session.scalar(text("SELECT count(*) FROM maintenance_batches")) == before_batches


def test_cluster_identity_unprivileged_access_and_fail_closed(maintenance_factory):  # noqa: F811
    factory = maintenance_factory
    with factory() as session:
        expected = maintenance._database_identity(session)
        # SET LOCAL changes only this connection, never any shared role or grant.
        session.execute(text("SET LOCAL ROLE pg_read_all_data"))
        assert maintenance._database_identity(session) == expected
    with factory() as session:
        # Function ACL is local to this disposable database and rolls back on exit.
        session.execute(
            text("REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM PUBLIC")
        )
        session.execute(text("SET LOCAL ROLE pg_read_all_data"))
        with pytest.raises(ValueError, match="^database_identity_unavailable$"):
            maintenance._database_identity(session)
    with factory() as session:
        assert maintenance._database_identity(session) == expected


def test_combined_cli_worker_preservation_and_damage_detection(
    maintenance_factory,  # noqa: F811
    tmp_path,
    monkeypatch,
    capsys,  # noqa: F811
):
    factory = maintenance_factory
    pending_executions = seed_pending_rewrite(factory)
    writeback_seed = seed_writeback_authority(factory, monkeypatch)
    before_writeback = _capture(factory, writeback_seed)
    active = seed_staging(factory)
    deleted = seed_staging(factory)
    blocked = seed_staging(factory)
    mark_deleted(factory, deleted.product_id)
    mark_deleted(factory, blocked.product_id)
    with factory.begin() as session:
        empty = Product(display_name="Empty deleted", name_key="empty-deleted")
        session.add(empty)
        session.flush()
        empty_id = empty.id
        session.execute(
            text(
                "INSERT INTO submission_reviews(id,actor_id,actor_token_version,product_id,"
                "revision_id,selection,input_digest,state,attempt,finished_at,expires_at) "
                "SELECT :id,deleted_by,0,id,active_revision_id,'[]',repeat('a',64),"
                "'failed',1,now(),now() FROM products WHERE id=:p"
            ),
            {"id": uuid4(), "p": blocked.product_id},
        )
    mark_deleted(factory, empty_id)
    workspace.SUPPORT.SUPPORT._configure_dependencies(factory)
    token = workspace.WORK.authority(factory, "admin")
    product, group, _ = workspace.WORK.seed(factory, target_revision=False)
    workspace.SEARCH._seed_pending_context(factory, group_id=group)
    page_response = workspace.request(token, product_id=product)
    detail_response = workspace.WORK.request(token, f"/{group}")
    assert page_response.status_code == detail_response.status_code == 200
    before_page = page_response.json()
    before_detail = detail_response.json()
    assert before_page["items"] and before_detail["source_context"]
    from tests.api.test_product_summary import request as summary_request

    summary_response = summary_request(token, active.product_id)
    assert summary_response.status_code == 200
    before_summary = summary_response.json()
    future = datetime.now(UTC) + timedelta(days=8)

    class Clock:
        @staticmethod
        def now(zone):
            return future

    monkeypatch.setattr(cli, "datetime", Clock)
    monkeypatch.setattr(worker, "datetime", Clock)
    monkeypatch.setattr(worker, "SessionFactory", factory)
    requested = [deleted.product_id, empty_id, blocked.product_id]
    path = tmp_path / "manifest.json"
    args = ["maintenance", "dry-run", "--temporary", "--output", str(path)]
    for product_id in requested:
        args.extend(["--product-id", str(product_id)])
    args.extend(["--batch-rows", "3", "--max-rows-per-run", "3"])
    assert cli.main(args, session_provider=factory) == 0
    manifest = maintenance.MaintenanceManifest.model_validate_json(path.read_text())
    assert {pending_executions[1].execution_id} <= {
        exclusion.id for exclusion in manifest.exclusions if exclusion.reason == "pending_rewrite"
    }
    before = evidence.snapshot(factory, manifest)
    apply_args = [
        "maintenance",
        "apply",
        "--manifest",
        str(path),
        "--digest",
        manifest.digest,
        "--batch-rows",
        "3",
        "--max-rows-per-run",
        "3",
    ]
    with factory() as other:
        other.execute(text("SELECT pg_advisory_lock(:key)"), {"key": maintenance.MAINTENANCE_LOCK})
        try:
            assert cli.main(apply_args, session_provider=factory) == 2
            assert json.loads(capsys.readouterr().out)["reason"] == "busy"
        finally:
            other.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": maintenance.MAINTENANCE_LOCK}
            )
    assert cli.main(apply_args, session_provider=factory) == 2
    partial = evidence.compare(before, evidence.snapshot(factory, manifest), manifest, requested)
    assert not partial["ok"]
    assert "incomplete" in {row["outcome"] for row in partial["products"]}
    for _ in range(60):
        if cli.main(apply_args, session_provider=factory) == 0:
            break
    else:
        pytest.fail("bounded maintenance did not complete")
    after = evidence.snapshot(factory, manifest)
    report = evidence.compare(before, after, manifest, requested)
    assert report["ok"], report
    assert sorted(row["outcome"] for row in report["products"]) == ["purged", "purged", "retained"]
    assert before["protected"]["import_source_references"]["count"] > 0
    assert before["protected"]["translation_proposals"]["count"] > 0
    assert before["protected"]["import_rewrite_proposals"]["count"] == 1
    assert workspace.request(token, product_id=product).json() == before_page
    assert workspace.WORK.request(token, f"/{group}").json() == before_detail
    assert summary_request(token, active.product_id).json() == before_summary
    assert _capture(factory, writeback_seed) == before_writeback
    with factory() as session:
        scheduled = maintenance.build_manifest(
            session, maintenance.MaintenancePolicy(), [], future, scheduled=True
        )
    worker_before = evidence.snapshot(factory, scheduled)
    assert worker.run_database_maintenance.run()["status"] == "complete"
    worker_after = evidence.snapshot(factory, scheduled)
    assert evidence.compare(worker_before, worker_after, scheduled)["ok"]
    assert not evidence.compare(before, after, manifest, requested + [uuid4()])["ok"]
    assert not evidence.compare(before, after, manifest, requested[:-1])["ok"]
    tampered = deepcopy(after)
    tampered["receipts"] = {}
    assert not evidence.compare(before, tampered, manifest, requested)["ok"]
    wrong_database = manifest.model_copy(update={"database_identity": "0" * 64})
    with pytest.raises(ValueError):
        evidence.snapshot(factory, wrong_database)
    with factory.begin() as session:
        session.get_one(Product, active.product_id).display_name = "Deliberate damage"
    damaged = evidence.snapshot(factory, manifest)
    assert not evidence.compare(before, damaged, manifest, requested)["ok"]
    assert "protected:products" in evidence.compare(before, damaged, manifest, requested)["errors"]
    content = json.dumps(after)
    assert "encrypted-access" not in content and "Original" not in content
    output = tmp_path / "evidence.json"
    evidence.write_private(output, after)
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        evidence.write_private(output, after)
    app.dependency_overrides.clear()
