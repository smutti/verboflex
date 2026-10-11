"""Review regressions use a fresh owned database per case, with all guards enabled."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, text

from tests.integration.test_database_maintenance import (
    _start_refresh_execution,
    maintenance_factory,
    seed_staging,
)
from verboflex.models.product import Product, ProductRevision
from verboflex.models.user import User
from verboflex.services import database_maintenance as maintenance


@pytest.fixture
def review_factory():
    # Reuse the generated-database setup/cleanup, without sharing prior test data.
    yield from maintenance_factory.__wrapped__()


def test_product_counts_join_owned_graph_without_correlated_row_lookups(review_factory):
    factory = review_factory
    identities = [seed_staging(factory), seed_staging(factory)]
    parsing = [_start_refresh_execution(factory, identity) for identity in identities]
    with factory.begin() as session:
        for identity, parse_execution in zip(identities, parsing, strict=True):
            preview = uuid4()
            session.execute(
                text(
                    "INSERT INTO preview_jobs(id,input_digest,attempt,state,revision_scope,"
                    "product_id,candidate_revision_id,candidate_revision_version,mapping_id,"
                    "topology,connection_generation,detector_version,layout_identity,"
                    "repository_sides) "
                    "SELECT :id,replace(CAST(:id AS text),'-','') || "
                    "replace(CAST(:id AS text),'-',''),1,'queued','active_revalidation',"
                    "product_id,revision_id,1,mapping_id,topology,1,'test','test','[]' "
                    "FROM import_jobs WHERE id=:job"
                ),
                {"id": preview, "job": identity.import_id},
            )
            session.execute(
                text(
                    "INSERT INTO translation_parse_issues(import_execution_id,position,"
                    "import_job_id,repository_side,path,issue_code,message) "
                    "VALUES(:execution,0,:job,'direct','test.json','malformed_file','Fixture')"
                ),
                {"execution": parse_execution.execution_id, "job": identity.import_id},
            )
            for owner_column, owner_id in (
                ("execution_id", identity.execution_id),
                ("preview_job_id", preview),
            ):
                report = uuid4()
                session.execute(
                    text(
                        f"INSERT INTO duplicate_reports(id,{owner_column},complete,issue_codes,"
                        "group_count,repeated_occurrences,sources) "
                        "VALUES(:report,:owner,true,'[]',1,2,'[]')"
                    ),
                    {"report": report, "owner": owner_id},
                )
                session.execute(
                    text(
                        "INSERT INTO duplicate_groups(report_id,position,identity_digest,"
                        "repository_side,"
                        "layout_identity,language,key_preview,key_length,occurrence_count) "
                        "VALUES(:report,0,repeat('a',64),'direct','test','en','key',3,2)"
                    ),
                    {"report": report},
                )
                session.execute(
                    text(
                        "INSERT INTO duplicate_occurrences(report_id,group_position,position,path,"
                        "resource_position) VALUES(:report,0,0,'test.json',0),"
                        "(:report,0,1,'test.json',1)"
                    ),
                    {"report": report},
                )

    statements = []
    engine = factory.kw["bind"]

    def observe(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT count(*) FROM"):
            statements.append(statement)

    def nodes(plan):
        yield plan
        for child in plan.get("Plans", []):
            yield from nodes(child)

    for product in [identity.product_id for identity in identities] + [uuid4()]:
        with factory() as session:
            expected = {
                table: session.scalar(
                    text(f"SELECT count(*) FROM {table} t WHERE {owner}=:product"),
                    {"product": product},
                )
                for table, owner in maintenance.OWNERS.items()
            }
            statements.clear()
            event.listen(engine, "before_cursor_execute", observe)
            try:
                actual = maintenance._product_counts(session, product)
            finally:
                event.remove(engine, "before_cursor_execute", observe)
            assert actual == expected
            if product in {identity.product_id for identity in identities}:
                assert actual["translation_values"] == actual["staged_translation_values"] == 2
                assert actual["translation_parse_issues"] == 1
                assert actual["duplicate_reports"] == actual["duplicate_groups"] == 2
                assert actual["duplicate_occurrences"] == 4
            for statement in statements:
                table = statement.split()[3]
                if maintenance.OWNERS[table] not in (
                    maintenance.KEY_OWNER,
                    maintenance.EXEC_OWNER,
                    maintenance.REPORT_OWNER,
                ) and table not in ("duplicate_reports", "import_source_references"):
                    continue
                plan = (
                    session.connection()
                    .exec_driver_sql(
                        "EXPLAIN (ANALYZE, FORMAT JSON) " + statement, {"product": product}
                    )
                    .scalar_one()[0]["Plan"]
                )
                assert not any(node.get("Parent Relationship") == "SubPlan" for node in nodes(plan))


def test_restored_foreign_pending_run_does_not_poison_scheduler(review_factory):
    factory = review_factory
    staged = seed_staging(factory)
    policy = maintenance.MaintenancePolicy(batch_rows=1, max_rows_per_run=1)
    now = datetime.now(UTC) + timedelta(days=8)
    with factory() as session:
        local = maintenance.build_manifest(session, policy, [], now, scheduled=True)
    foreign = local.model_copy(update={"database_identity": "0" * 64})
    foreign = foreign.model_copy(update={"digest": foreign.calculated_digest()})
    with factory.begin() as session:
        session.execute(
            text(
                "INSERT INTO maintenance_runs(digest,manifest,status,error_code) "
                "VALUES(:d,CAST(:m AS jsonb),'partial','budget')"
            ),
            {"d": foreign.digest, "m": foreign.model_dump_json()},
        )
        session.execute(
            text(
                "INSERT INTO maintenance_batches(run_digest,kind,target_id,counts) "
                "VALUES(:d,'staging',:id,jsonb_build_object('staged_translation_values',1))"
            ),
            {"d": foreign.digest, "id": staged.execution_id},
        )

    def foreign_audit():
        with factory() as session:
            return tuple(
                session.scalars(text(query), {"d": foreign.digest}).all()
                for query in (
                    "SELECT to_jsonb(r) FROM maintenance_runs r WHERE digest=:d",
                    "SELECT to_jsonb(b) FROM maintenance_batches b WHERE run_digest=:d ORDER BY id",
                )
            )

    before = foreign_audit()
    with pytest.raises(ValueError, match="database_or_schema_mismatch"):
        maintenance.apply_manifest(factory, foreign, policy, now)
    assert foreign_audit() == before
    first = maintenance.run_scheduled_maintenance(factory, policy, now)
    second = maintenance.run_scheduled_maintenance(factory, policy, now + timedelta(minutes=1))
    assert first.status == "partial" and first.deleted_rows == 1
    assert second.status == "complete" and second.deleted_rows == 1
    assert first.digest == second.digest != foreign.digest
    assert foreign_audit() == before
    with factory() as session:
        assert maintenance._staging_count(session, staged.execution_id) == 0


def test_protected_thousand_execution_prefix_does_not_starve_eligible_tail(review_factory):
    factory = review_factory
    protected = seed_staging(factory)
    eligible = seed_staging(factory)
    with factory.begin() as session:
        # Copy only into fresh owned rows. Staging is inserted while each execution is running,
        # then completed through the normal immutable guards; no trigger bypass is used.
        session.execute(
            text(
                "INSERT INTO import_executions SELECT clone.* FROM import_executions template "
                "CROSS JOIN generate_series(1,1000) n CROSS JOIN LATERAL "
                "jsonb_populate_record(NULL::import_executions, to_jsonb(template) || "
                "jsonb_build_object('id',lpad(to_hex(n),32,'0')::uuid,'sequence',n+1,"
                "'state','running','finished_at',NULL)) clone WHERE template.id=:id"
            ),
            {"id": protected.execution_id},
        )
        session.execute(
            text(
                "INSERT INTO import_source_references SELECT clone.* "
                "FROM import_source_references template CROSS JOIN generate_series(1,1000) n "
                "CROSS JOIN LATERAL jsonb_populate_record(NULL::import_source_references, "
                "to_jsonb(template) || jsonb_build_object('execution_id',"
                "lpad(to_hex(n),32,'0')::uuid)) clone WHERE template.execution_id=:id"
            ),
            {"id": protected.execution_id},
        )
        staged_columns = [
            f'"{column.name}"'
            for column in maintenance.Base.metadata.tables["staged_translation_values"].columns
            if column.computed is None
        ]
        session.execute(
            text(
                "INSERT INTO staged_translation_values ("
                + ", ".join(staged_columns)
                + ") SELECT "
                + ", ".join(f"clone.{column}" for column in staged_columns)
                + " "
                "FROM staged_translation_values template CROSS JOIN generate_series(1,1000) n "
                "CROSS JOIN LATERAL jsonb_populate_record(NULL::staged_translation_values, "
                "to_jsonb(template) || jsonb_build_object('import_execution_id',"
                "lpad(to_hex(n),32,'0')::uuid)) clone WHERE template.import_execution_id=:id"
            ),
            {"id": protected.execution_id},
        )
        session.execute(
            text(
                "UPDATE import_executions SET state='succeeded',finished_at=now() "
                "WHERE import_job_id=:job AND id<>:id"
            ),
            {"job": protected.import_id, "id": protected.execution_id},
        )
        session.execute(
            text(
                "INSERT INTO import_executions SELECT clone.* FROM import_executions template "
                "CROSS JOIN LATERAL jsonb_populate_record(NULL::import_executions, "
                "to_jsonb(template) || jsonb_build_object('id',CAST(:new AS uuid),'sequence',1002,"
                "'state','running','finished_at',NULL)) clone WHERE template.id=:id"
            ),
            {"id": protected.execution_id, "new": uuid4()},
        )
    now = datetime.now(UTC) + timedelta(days=8)
    policy = maintenance.MaintenancePolicy()
    with factory() as session:
        manifest = maintenance.build_manifest(session, policy, [], now, scheduled=True)
        assert [target.id for target in manifest.targets] == [eligible.execution_id]
        assert len(manifest.exclusions) == 1000
        assert {item.reason for item in manifest.exclusions} == {"inflight"}
        before = session.scalar(text("SELECT count(*) FROM staged_translation_values"))
    first = maintenance.run_scheduled_maintenance(factory, policy, now)
    second = maintenance.run_scheduled_maintenance(factory, policy, now + timedelta(minutes=1))
    assert first.status == second.status == "complete"
    assert first.deleted_rows == 2 and second.deleted_rows == 0
    with factory() as session:
        assert maintenance._staging_count(session, eligible.execution_id) == 0
        assert session.scalar(text("SELECT count(*) FROM staged_translation_values")) == before - 2
        assert maintenance._staging_count(session, UUID(int=1000)) == 2


def test_hundred_evidence_protected_products_do_not_starve_eligible_tail(review_factory):
    factory = review_factory
    now = datetime.now(UTC)
    protected_ids = [UUID(int=n) for n in range(1, 101)]
    eligible_id = uuid4()
    with factory.begin() as session:
        actor = User(email="review@example.com", display_name="Review", hashed_password="test-only")
        session.add(actor)
        session.flush()
        for product_id in [*protected_ids, eligible_id]:
            session.add(
                Product(
                    id=product_id,
                    display_name=str(product_id),
                    name_key=str(product_id),
                    deleted_by=actor.id,
                    deleted_at=now - timedelta(days=40 if product_id in protected_ids else 31),
                    is_active=False,
                )
            )
        session.flush()
        for product_id in protected_ids:
            revision = ProductRevision(product_id=product_id)
            session.add(revision)
            session.flush()
            session.execute(
                text(
                    "INSERT INTO submission_reviews(id,actor_id,actor_token_version,product_id,"
                    "revision_id,selection,input_digest,state,attempt,finished_at,expires_at) "
                    "VALUES(:id,:actor,0,:p,:r,'[]',repeat('a',64),'failed',1,now(),now())"
                ),
                {"id": uuid4(), "actor": actor.id, "p": product_id, "r": revision.id},
            )
    policy = maintenance.MaintenancePolicy(deleted_product_retention_days=30)
    with factory() as session:
        manifest = maintenance.build_manifest(session, policy, [], now, scheduled=True)
        assert [target.id for target in manifest.targets] == [eligible_id]
        assert {item.id for item in manifest.exclusions} == set(protected_ids)
        assert {item.reason for item in manifest.exclusions} == {"submission_evidence"}
        reviews_before = session.scalars(
            text("SELECT to_jsonb(r) FROM submission_reviews r ORDER BY id")
        ).all()
    first = maintenance.run_scheduled_maintenance(factory, policy, now)
    second = maintenance.run_scheduled_maintenance(factory, policy, now + timedelta(minutes=1))
    assert first.status == second.status == "complete"
    assert first.deleted_rows == 1 and second.deleted_rows == 0
    with factory() as session:
        assert session.get(Product, eligible_id) is None
        assert set(session.scalars(text("SELECT id FROM products"))) == set(protected_ids)
        assert (
            session.scalars(text("SELECT to_jsonb(r) FROM submission_reviews r ORDER BY id")).all()
            == reviews_before
        )
