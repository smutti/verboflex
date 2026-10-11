"""Maintenance is exercised only in a newly created, explicitly owned database."""

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from tests.integration.test_translation_import_activation import (
    _json_result,
    _reconcile_staged_result,
    _seed_running_direct_import,
    _stage_direct_manifest,
    _start_refresh_execution,
)
from tests.legacy_product_fixtures import shared_product_fixture
from verboflex.integrations.bitbucket.client import BitbucketFileDelta
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.import_job import ImportExecution, ImportJob
from verboflex.models.product import Product
from verboflex.models.user import User
from verboflex.services import database_maintenance as maintenance
from verboflex.services import import_jobs
from verboflex.services.bitbucket_oauth import PULLREQUEST_WRITE_SCOPE


@pytest.fixture(scope="module")
def maintenance_factory() -> Iterator[sessionmaker[Session]]:
    admin_url = os.environ["VERBOFLEX_TEST_POSTGRES_ADMIN_URL"]
    name = "verboflex_maintenance_" + uuid4().hex
    with connect(admin_url, autocommit=True, connect_timeout=5) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = admin_url.rsplit("/", 1)[0] + "/" + name
    url = url.replace("postgresql://", "postgresql+psycopg://")
    config = Config(Path(__file__).resolve().parents[2] / "alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        # env.py prefers this variable: explicitly bind it to the owned database.
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("VERBOFLEX_DATABASE_URL", url)
            command.upgrade(config, "head")
        factory = sessionmaker(engine, expire_on_commit=False)
        shared_product_fixture(factory)
        with factory.begin() as session:
            connection = session.get_one(BitbucketConnection, 1)
            connection.generation = 9
            connection.access_token_ciphertext = "encrypted-access"
            connection.scope_profile = PULLREQUEST_WRITE_SCOPE
            connection.provider_expires_at = datetime.now(UTC) + timedelta(hours=1)
            connection.connected_at = datetime.now(UTC)
            connection.revoked_at = None
        yield factory
    finally:
        engine.dispose()
        with connect(admin_url, autocommit=True, connect_timeout=5) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def seed_staging(factory):
    identity, repository = _seed_running_direct_import(factory)
    _reconcile_staged_result(
        factory, identity=identity, repository_id=repository, result=_json_result()
    )
    with factory.begin() as session:
        execution = session.get_one(ImportExecution, identity.execution_id)
        execution.state = "succeeded"
        execution.finished_at = datetime.now(UTC)
        job = session.get_one(ImportJob, identity.import_id)
        job.state = "current"
        job.active_baseline_execution_id = identity.execution_id
    return identity


def test_staging_dry_run_apply_resume_preserves_canonical(maintenance_factory):
    factory = maintenance_factory
    identity = seed_staging(factory)
    now = datetime.now(UTC) + timedelta(days=8)
    policy = maintenance.MaintenancePolicy(batch_rows=1, max_rows_per_run=1)
    with factory() as session:
        before = session.scalar(text("SELECT count(*) FROM translation_values"))
        runs_before = session.scalar(text("SELECT count(*) FROM maintenance_runs"))
        manifest = maintenance.build_manifest(session, policy, [], now)
        assert session.scalar(text("SELECT count(*) FROM maintenance_runs")) == runs_before
    summary = maintenance.apply_manifest(factory, manifest, policy, now)
    assert summary.deleted_rows == 1
    for _ in range(100):
        summary = maintenance.apply_manifest(factory, manifest, policy, now)
        if summary.status == "complete":
            break
    assert summary.status == "complete"
    assert maintenance.apply_manifest(factory, manifest, policy, now).deleted_rows == 0
    with factory() as session:
        assert session.scalar(text("SELECT count(*) FROM translation_values")) == before
        assert session.get_one(ImportExecution, identity.execution_id).state == "succeeded"
        assert session.scalar(text("SELECT count(*) FROM import_source_references")) > 0


def test_inflight_staging_remains_immutable(maintenance_factory):
    factory = maintenance_factory
    identity, repository = _seed_running_direct_import(factory)
    _stage_direct_manifest(
        factory, identity=identity, repository_id=repository, result=_json_result()
    )
    for statement in (
        "DELETE FROM staged_translation_values WHERE import_execution_id=:id",
        "UPDATE staged_translation_values SET display_text='forged' WHERE import_execution_id=:id",
    ):
        with pytest.raises(DBAPIError), factory.begin() as session:
            session.execute(text("SET LOCAL verboflex.maintenance = 'true'"))
            session.execute(text(statement), {"id": identity.execution_id})


def test_staging_manifest_tampering_rejected(maintenance_factory):
    with maintenance_factory() as session:
        policy = maintenance.MaintenancePolicy()
        manifest = maintenance.build_manifest(session, policy, [], datetime.now(UTC))
    data = manifest.model_dump(mode="json")
    data["untrusted"] = "SELECT * FROM users"
    with pytest.raises(ValueError):
        maintenance.MaintenanceManifest.model_validate(data)
    with pytest.raises(ValueError):
        maintenance.MaintenancePolicy(batch_rows=0)


def test_staging_rollback_and_concurrent_run(maintenance_factory, monkeypatch):
    factory = maintenance_factory
    seed_staging(factory)
    now = datetime.now(UTC) + timedelta(days=8)
    policy = maintenance.MaintenancePolicy()
    with factory() as session:
        manifest = maintenance.build_manifest(session, policy, [], now)
    with factory() as other:
        other.execute(text("SELECT pg_advisory_lock(:key)"), {"key": maintenance.MAINTENANCE_LOCK})
        try:
            assert maintenance.apply_manifest(factory, manifest, policy, now).status == "skipped"
        finally:
            other.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": maintenance.MAINTENANCE_LOCK}
            )
    original = maintenance._staging_batch

    def crash(*args):
        original(*args)
        raise ValueError("injected")

    with monkeypatch.context() as patch:
        patch.setattr(maintenance, "_staging_batch", crash)
        assert maintenance.apply_manifest(factory, manifest, policy, now).deleted_rows == 0
    with factory() as session:
        assert (
            session.scalar(
                text("SELECT count(*) FROM maintenance_batches WHERE run_digest=:d"),
                {"d": manifest.digest},
            )
            == 0
        )
        assert session.scalar(text("SELECT count(*) FROM maintenance_authorizations")) == 0
    assert maintenance.apply_manifest(factory, manifest, policy, now).status == "complete"


def mark_deleted(factory, product_id):
    with factory.begin() as session:
        actor = User(
            email=f"maintenance-{uuid4()}@example.com",
            display_name="Operator",
            hashed_password="test-only",
        )
        session.add(actor)
        session.flush()
        product = session.get_one(Product, product_id)
        product.is_active = False
        product.deleted_at = datetime.now(UTC)
        product.deleted_by = actor.id


def test_product_purge_resume_preserves_active_graph(maintenance_factory):
    factory = maintenance_factory
    deleted = seed_staging(factory)
    active = seed_staging(factory)
    mark_deleted(factory, deleted.product_id)
    now = datetime.now(UTC) + timedelta(days=8)
    policy = maintenance.MaintenancePolicy(batch_rows=3, max_rows_per_run=3)
    with factory() as session:
        manifest = maintenance.build_manifest(
            session, policy, [deleted.product_id], now, temporary=False
        )
        assert not manifest.exclusions
        expected = sum(manifest.targets[0].counts.values())
        before = session.scalar(
            text(
                "SELECT md5(string_agg(to_jsonb(v)::text, '' ORDER BY v.id)) "
                "FROM translation_values v JOIN translation_keys k "
                "ON k.id=v.translation_key_id WHERE k.product_id=:p"
            ),
            {"p": active.product_id},
        )
    total = 0
    for _ in range(40):
        summary = maintenance.apply_manifest(factory, manifest, policy, now)
        assert summary.deleted_rows <= 3
        total += summary.deleted_rows
        if summary.status == "complete":
            break
    assert summary.status == "complete", summary
    assert total == expected
    with factory() as session:
        assert session.get(Product, deleted.product_id) is None
        assert session.get(Product, active.product_id).is_active
        assert (
            session.scalar(
                text(
                    "SELECT md5(string_agg(to_jsonb(v)::text, '' ORDER BY v.id)) "
                    "FROM translation_values v JOIN translation_keys k "
                    "ON k.id=v.translation_key_id WHERE k.product_id=:p"
                ),
                {"p": active.product_id},
            )
            == before
        )


def test_product_active_and_unknown_fk_fail_closed(maintenance_factory):
    factory = maintenance_factory
    identity = seed_staging(factory)
    policy = maintenance.MaintenancePolicy()
    now = datetime.now(UTC)
    with factory() as session:
        manifest = maintenance.build_manifest(
            session, policy, [identity.product_id], now, temporary=False
        )
        assert manifest.exclusions[0].reason == "not_deleted"
    mark_deleted(factory, identity.product_id)
    with factory() as session:
        manifest = maintenance.build_manifest(
            session, policy, [identity.product_id], now, temporary=False
        )
    with factory.begin() as session:
        session.execute(
            text(
                "CREATE TABLE unexpected_reference (id uuid PRIMARY KEY, "
                "product_id uuid REFERENCES products(id) ON DELETE CASCADE)"
            )
        )
    try:
        with pytest.raises(ValueError, match="schema"):
            maintenance.apply_manifest(factory, manifest, policy, now)
    finally:
        with factory.begin() as session:
            session.execute(text("DROP TABLE unexpected_reference"))


def test_product_review_evidence_and_submission_exclusion(maintenance_factory):
    factory = maintenance_factory
    identity = seed_staging(factory)
    mark_deleted(factory, identity.product_id)
    ids = {
        key: uuid4()
        for key in (
            "proposal",
            "comment",
            "version",
            "mention",
            "notification",
            "activity",
            "proposal_value",
            "constraint",
        )
    }
    with factory.begin() as session:
        recipient = User(
            email=f"recipient-{uuid4()}@example.com",
            display_name="Recipient",
            hashed_password="test-only",
        )
        session.add(recipient)
        session.flush()
        ids["recipient"] = recipient.id
        row = (
            session.execute(
                text(
                    "SELECT k.id AS key, k.scope_id AS scope, v.id AS value, "
                    "v.selector_digest AS selector, p.deleted_by AS actor FROM translation_keys k "
                    "JOIN translation_values v ON v.translation_key_id=k.id JOIN products p "
                    "ON p.id=k.product_id WHERE p.id=:p AND v.language='it'"
                ),
                {"p": identity.product_id},
            )
            .mappings()
            .one()
        )
        ids.update(row)
        statements = (
            "INSERT INTO translation_proposals(id,scope_id,translation_key_id,language,version,"
            "state,created_by,updated_by) "
            "VALUES(:proposal,:scope,:key,'it',1,'draft',:actor,:actor)",
            "INSERT INTO translation_proposal_values(id,proposal_id,translation_key_id,language,"
            "translation_value_id,selector_version,selector_digest,basis_revision_number,basis_digest,"
            "proposed_text,grapheme_count) "
            "VALUES(:proposal_value,:proposal,:key,'it',:value,1,:selector,"
            "0,repeat('a',64),'Edited',6)",
            "INSERT INTO translation_comments(id,scope_id,translation_key_id,language,author_id,"
            "current_version) VALUES(:comment,:scope,:key,'it',:actor,1)",
            "INSERT INTO translation_comment_versions(id,comment_id,translation_key_id,language,"
            "version_number,body,author_id) "
            "VALUES(:version,:comment,:key,'it',1,'@Operator',:actor)",
            "INSERT INTO translation_comment_mentions(id,comment_version_id,mentioned_user_id,"
            "start_utf16,end_utf16,display_text) VALUES(:mention,:version,:actor,0,9,'@Operator')",
            "INSERT INTO notifications(id,recipient_user_id,actor_user_id,"
            "originating_comment_id,kind) "
            "VALUES(:notification,:recipient,:actor,:comment,'mention')",
            "INSERT INTO review_activities(id,proposal_id,translation_key_id,language,kind,"
            "proposal_version,to_state,actor_id,comment_id) VALUES(:activity,:proposal,:key,'it',"
            "'proposal_saved',1,'draft',:actor,:comment)",
            "INSERT INTO translation_constraints(id,scope_id,translation_key_id,language,max_chars,"
            "created_by,updated_by) VALUES(:constraint,:scope,:key,'it',20,:actor,:actor)",
        )
        for statement in statements:
            session.execute(text(statement), ids)
    with pytest.raises(DBAPIError), factory.begin() as session:
        session.execute(text("DELETE FROM translation_comment_versions WHERE id=:version"), ids)
    policy = maintenance.MaintenancePolicy(batch_rows=4, max_rows_per_run=100)
    now = datetime.now(UTC)
    with factory() as session:
        manifest = maintenance.build_manifest(
            session, policy, [identity.product_id], now, temporary=False
        )
    result = maintenance.apply_manifest(factory, manifest, policy, now)
    assert result.status == "complete", result
    assert result.counts["translation_comment_versions"] == 1
    assert result.counts["translation_comment_mentions"] == 1
    assert result.counts["review_activities"] == 1
    assert result.counts["notifications"] == 1
    with factory() as session:
        assert session.get(User, ids["actor"]) is not None

    protected = seed_staging(factory)
    mark_deleted(factory, protected.product_id)
    with factory.begin() as session:
        session.execute(
            text(
                "INSERT INTO submission_reviews (id,actor_id,actor_token_version,"
                "product_id,revision_id,selection,input_digest,state,attempt,finished_at,expires_at)"
                " SELECT :id,deleted_by,0,id,active_revision_id,'[]',repeat('a',64),"
                "'failed',1,now(),now() "
                "FROM products WHERE id=:p"
            ),
            {"id": uuid4(), "p": protected.product_id},
        )
    with factory() as session:
        manifest = maintenance.build_manifest(
            session, policy, [protected.product_id], now, temporary=False
        )
        assert manifest.exclusions[0].reason == "submission_evidence"
        assert not manifest.targets


def test_immutable_authority_wrong_transaction_cross_product_and_partial_key(maintenance_factory):
    factory = maintenance_factory
    first, second = seed_staging(factory), seed_staging(factory)
    mark_deleted(factory, first.product_id)
    now = datetime.now(UTC) + timedelta(days=8)
    policy = maintenance.MaintenancePolicy()
    with factory() as session:
        manifest = maintenance.build_manifest(
            session, policy, [first.product_id], now, temporary=False
        )
    with factory.begin() as session:
        session.execute(
            text(
                "INSERT INTO maintenance_runs(digest,manifest,status) "
                "VALUES(:d,CAST(:m AS jsonb),'running')"
            ),
            {"d": manifest.digest, "m": manifest.model_dump_json()},
        )
    for transaction, key in (
        ("'0'", {"id": str(first.execution_id)}),
        ("pg_current_xact_id()::text", {"id": str(second.execution_id)}),
        ("pg_current_xact_id()::text", {"import_job_id": str(first.import_id)}),
    ):
        with pytest.raises(DBAPIError), factory.begin() as session:
            session.execute(
                text(
                    "INSERT INTO maintenance_authorizations "
                    "(transaction_id,run_digest,kind,target_id,product_id,table_name,row_key) "
                    f"VALUES({transaction},:d,'product',:p,:p,"
                    "'import_executions',CAST(:key AS jsonb))"
                ),
                {"d": manifest.digest, "p": first.product_id, "key": json.dumps(key)},
            )


def test_migration_roundtrip_restores_exact_guards(maintenance_factory):
    engine = maintenance_factory.kw["bind"]
    config = Config(Path(__file__).resolve().parents[2] / "alembic.ini")
    url = engine.url.render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    with engine.connect() as connection:
        originals = dict(
            connection.execute(
                text(
                    "SELECT name, original_definition "
                    "FROM maintenance_schema WHERE name NOT IN ('foreign_keys','triggers') "
                    "AND name NOT LIKE 'verboflex_maintenance_%'"
                )
            ).all()
        )
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("VERBOFLEX_DATABASE_URL", url)
        command.downgrade(config, "0031_change_sets")
        with engine.connect() as connection:
            for name, original in originals.items():
                assert (
                    connection.scalar(
                        text("SELECT pg_get_functiondef(to_regproc(:name))"), {"name": name}
                    )
                    == original
                )
        command.upgrade(config, "head")


def test_staging_pending_rewrite_and_concurrent_product_change(maintenance_factory):
    factory = maintenance_factory
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
    movement = import_jobs.SourceMovementClassification(
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
    )
    assert import_jobs.finish_import_execution(
        factory,
        identity=second,
        references=references,
        movement=movement,
        canonical_manifest_digest=staged.digest,
    )
    now = datetime.now(UTC) + timedelta(days=8)
    policy = maintenance.MaintenancePolicy()
    with factory() as session:
        manifest = maintenance.build_manifest(session, policy, [], now)
        protected = {item.id for item in manifest.exclusions if item.reason == "pending_rewrite"}
        assert second.execution_id in protected
    maintenance.apply_manifest(factory, manifest, policy, now)
    with factory() as session:
        assert maintenance._staging_count(session, first.execution_id) == 0
        assert maintenance._staging_count(session, second.execution_id) == 2
    mark_deleted(factory, first.product_id)
    with factory() as session:
        manifest = maintenance.build_manifest(
            session, policy, [first.product_id], now, temporary=False
        )
        assert manifest.exclusions[0].reason == "pending_rewrite"

    changed = seed_staging(factory)
    mark_deleted(factory, changed.product_id)
    with factory() as session:
        manifest = maintenance.build_manifest(
            session, policy, [changed.product_id], now, temporary=False
        )
    with factory.begin() as session:
        product = session.get_one(Product, changed.product_id)
        product.deleted_at = product.deleted_by = None
        product.is_active = True
    result = maintenance.apply_manifest(factory, manifest, policy, now)
    assert result.deleted_rows == 0 and result.reason == "not_deleted"
