"""Exact transaction-scoped maintenance deletion and durable content-free receipts."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0032_database_maintenance"
down_revision: str | None = "0031_change_sets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUARDS = (
    "verboflex_guard_canonical_staging",
    "verboflex_guard_active_revision_child",
    "verboflex_guard_terminal_import_execution",
    "verboflex_guard_import_source_reference",
    "verboflex_guard_import_rewrite_proposal",
    "verboflex_guard_import_rewrite_delta",
    "verboflex_guard_translation_value_revision_immutable",
    "verboflex_guard_review_evidence_immutable",
    "verboflex_guard_active_revalidation_confirmation",
)

CYCLIC_FKS = (
    (
        "import_jobs",
        "fk_import_jobs_current_execution",
        "current_execution_id, id",
        "import_executions",
        "id, import_job_id",
    ),
    (
        "import_jobs",
        "fk_import_jobs_active_baseline",
        "active_baseline_execution_id, id",
        "import_executions",
        "id, import_job_id",
    ),
    ("product_repository_mappings", None, "confirmed_preview_job_id", "preview_jobs", "id"),
)

# Closed ownership graph: expressions use only the fixed table alias t.
KEY_OWNER = "(SELECT product_id FROM translation_keys WHERE id=t.translation_key_id)"
EXEC_OWNER = (
    "(SELECT j.product_id FROM import_executions e JOIN import_jobs j "
    "ON j.id=e.import_job_id WHERE e.id=t.import_execution_id)"
)
REPORT_OWNER = (
    "(SELECT coalesce(j.product_id,p.product_id) FROM duplicate_reports d "
    "LEFT JOIN import_executions e ON e.id=d.execution_id "
    "LEFT JOIN import_jobs j ON j.id=e.import_job_id "
    "LEFT JOIN preview_jobs p ON p.id=d.preview_job_id WHERE d.id=t.report_id)"
)
OWNERS = {
    "notifications": "(SELECT k.product_id FROM translation_comments c JOIN translation_keys k "
    "ON k.id=c.translation_key_id WHERE c.id=t.originating_comment_id)",
    "translation_comment_mentions": "(SELECT k.product_id FROM translation_comment_versions v "
    "JOIN translation_comments c ON c.id=v.comment_id JOIN translation_keys k "
    "ON k.id=c.translation_key_id WHERE v.id=t.comment_version_id)",
    "translation_comment_versions": "(SELECT k.product_id FROM translation_comments c "
    "JOIN translation_keys k ON k.id=c.translation_key_id WHERE c.id=t.comment_id)",
    "review_activities": "(SELECT k.product_id FROM translation_proposals p "
    "JOIN translation_keys k ON k.id=p.translation_key_id WHERE p.id=t.proposal_id)",
    "translation_proposal_values": KEY_OWNER,
    "translation_comments": KEY_OWNER,
    "translation_proposals": KEY_OWNER,
    "translation_constraints": KEY_OWNER,
    "translation_value_locators": KEY_OWNER,
    "translation_value_revisions": KEY_OWNER,
    "translation_values": KEY_OWNER,
    "translation_keys": "t.product_id",
    "localization_scopes": "t.product_id",
    "staged_translation_values": EXEC_OWNER,
    "translation_parse_issues": EXEC_OWNER,
    "duplicate_occurrences": REPORT_OWNER,
    "duplicate_groups": REPORT_OWNER,
    "duplicate_reports": "coalesce((SELECT j.product_id FROM import_executions e "
    "JOIN import_jobs j ON j.id=e.import_job_id WHERE e.id=t.execution_id), "
    "(SELECT product_id FROM preview_jobs WHERE id=t.preview_job_id))",
    "import_rewrite_deltas": "(SELECT product_id FROM import_rewrite_proposals "
    "WHERE id=t.proposal_id)",
    "import_rewrite_proposals": "t.product_id",
    "import_source_references": EXEC_OWNER.replace("t.import_execution_id", "t.execution_id"),
    "import_executions": "(SELECT product_id FROM import_jobs WHERE id=t.import_job_id)",
    "import_jobs": "t.product_id",
    "active_revision_revalidation_confirmations": "t.product_id",
    "preview_jobs": "t.product_id",
    "product_mapping_repository_sides": "(SELECT r.product_id FROM product_repository_mappings m "
    "JOIN product_revisions r ON r.id=m.revision_id WHERE m.id=t.mapping_id)",
    "product_mapping_allowed_targets": "(SELECT r.product_id FROM product_repository_mappings m "
    "JOIN product_revisions r ON r.id=m.revision_id WHERE m.id=t.mapping_id)",
    "product_repository_mappings": (
        "(SELECT product_id FROM product_revisions WHERE id=t.revision_id)"
    ),
    "product_revisions": "t.product_id",
    "products": "t.id",
}
TRIGGER_CATALOG_SQL = """SELECT coalesce(jsonb_agg(jsonb_build_array(
    tgrelid::regclass::text, tgname, pg_get_triggerdef(oid))
    ORDER BY tgrelid::regclass::text, tgname), '[]'::jsonb)::text
    FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN
    (SELECT oid FROM pg_class WHERE relnamespace='public'::regnamespace)"""

FK_CATALOG_SQL = """SELECT coalesce(jsonb_agg(jsonb_build_array(
    conrelid::regclass::text, conname, pg_get_constraintdef(oid))
    ORDER BY conrelid::regclass::text, conname), '[]'::jsonb)::text
    FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace
    AND conrelid::regclass::text NOT LIKE 'maintenance_%'"""


ALLOW_SQL = """
CREATE FUNCTION verboflex_maintenance_delete_allowed(tab text, old_row jsonb)
RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE a record; e record; p record;
BEGIN
    FOR a IN SELECT auth.*, run.manifest FROM maintenance_authorizations auth
        JOIN maintenance_runs run ON run.digest = auth.run_digest
        WHERE auth.transaction_id = pg_current_xact_id()::text
        AND auth.table_name = tab AND old_row @> auth.row_key
        AND run.status = 'running'
    LOOP
        SELECT product.* INTO p FROM products product
        WHERE product.id = a.product_id FOR UPDATE;
        IF a.kind = 'product' AND a.target_id = p.id
           AND NOT p.is_active AND p.deleted_at IS NOT NULL
           AND NOT verboflex_maintenance_product_blocked(p.id)
           AND EXISTS (SELECT 1 FROM jsonb_array_elements(a.manifest->'targets') item
               WHERE item->>'kind'='product' AND item->>'id'=p.id::text
                 AND item->>'product_id'=p.id::text)
        THEN RETURN true; END IF;
        IF tab <> 'staged_translation_values' OR a.kind <> 'staging' THEN
            CONTINUE;
        END IF;
        SELECT execution.*, job.product_id INTO e FROM import_executions execution
        JOIN import_jobs job ON job.id = execution.import_job_id
        WHERE execution.id = (old_row->>'import_execution_id')::uuid
        FOR UPDATE OF execution;
        IF e.product_id = a.product_id AND e.id = a.target_id
           AND e.state IN ('succeeded', 'failed')
           AND e.finished_at < (a.manifest->>'temporary_cutoff')::timestamptz
           AND NOT EXISTS (SELECT 1 FROM import_rewrite_proposals r
               WHERE r.product_id = a.product_id AND r.status = 'pending')
           AND NOT EXISTS (SELECT 1 FROM import_jobs j
               WHERE j.product_id = a.product_id AND j.state IN ('queued', 'running'))
           AND NOT EXISTS (SELECT 1 FROM preview_jobs j
               WHERE j.product_id = a.product_id AND j.state IN ('queued', 'running'))
           AND NOT EXISTS (SELECT 1 FROM submission_reviews j
               WHERE j.product_id = a.product_id AND j.state IN ('queued', 'running'))
           AND EXISTS (SELECT 1 FROM jsonb_array_elements(a.manifest->'targets') item
               WHERE item->>'kind' = 'staging' AND item->>'id' = a.target_id::text
               AND item->>'product_id' = a.product_id::text)
        THEN RETURN true; END IF;
    END LOOP;
    RETURN false;
END $$
"""


BLOCKED_SQL = """
CREATE FUNCTION verboflex_maintenance_product_blocked(product uuid)
RETURNS boolean LANGUAGE sql AS $$
    SELECT EXISTS (SELECT 1 FROM import_jobs WHERE product_id=product
        AND state IN ('queued','running'))
    OR EXISTS (SELECT 1 FROM import_executions e JOIN import_jobs j ON j.id=e.import_job_id
        WHERE j.product_id=product AND e.state IN ('queued','running'))
    OR EXISTS (SELECT 1 FROM preview_jobs WHERE product_id=product
        AND state IN ('queued','running'))
    OR EXISTS (SELECT 1 FROM import_rewrite_proposals WHERE product_id=product AND status='pending')
    OR EXISTS (SELECT 1 FROM submission_reviews WHERE product_id=product)
    OR EXISTS (SELECT 1 FROM submission_batches WHERE product_id=product)
$$
"""

AUTHORIZE_SQL = """
CREATE FUNCTION verboflex_maintenance_authorize() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_product uuid; row_pk jsonb; target record; manifest jsonb;
BEGIN
    IF NEW.transaction_id <> pg_current_xact_id()::text
       OR NEW.table_name NOT IN (__TABLES__) THEN
        RAISE EXCEPTION 'invalid maintenance authority' USING ERRCODE='55000';
    END IF;
    SELECT run.manifest INTO manifest FROM maintenance_runs run
        WHERE digest=NEW.run_digest AND status='running';
    IF manifest IS NULL OR NOT EXISTS (
        SELECT 1 FROM jsonb_array_elements(manifest->'targets') item
        WHERE item->>'kind'=NEW.kind AND item->>'id'=NEW.target_id::text
        AND item->>'product_id'=NEW.product_id::text) THEN
        RAISE EXCEPTION 'invalid maintenance scope' USING ERRCODE='55000';
    END IF;
    SELECT jsonb_object_agg(a.attname, NEW.row_key->a.attname) INTO row_pk
        FROM pg_index i CROSS JOIN LATERAL unnest(i.indkey) key(attnum)
        JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=key.attnum
        WHERE i.indrelid=to_regclass(NEW.table_name) AND i.indisprimary;
    IF row_pk IS DISTINCT FROM NEW.row_key OR jsonb_path_exists(row_pk, '$.* ? (@ == null)') THEN
        RAISE EXCEPTION 'invalid maintenance row key' USING ERRCODE='55000';
    END IF;
    actual_product := verboflex_maintenance_row_owner(NEW.table_name, NEW.row_key);
    IF actual_product IS DISTINCT FROM NEW.product_id THEN
        RAISE EXCEPTION 'invalid maintenance row ownership' USING ERRCODE='55000';
    END IF;
    SELECT * INTO target FROM products WHERE id=actual_product FOR UPDATE;
    IF NEW.kind='product' THEN
        IF target.is_active OR target.deleted_at IS NULL OR NEW.target_id <> target.id
           OR verboflex_maintenance_product_blocked(target.id) THEN
            RAISE EXCEPTION 'ineligible maintenance product' USING ERRCODE='55000';
        END IF;
    ELSIF NEW.table_name <> 'staged_translation_values'
        OR NEW.target_id::text IS DISTINCT FROM NEW.row_key->>'import_execution_id' THEN
        RAISE EXCEPTION 'invalid maintenance staging scope' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END $$
"""


def _cycle_foreign_keys(maintenance: bool) -> None:
    connection = op.get_bind()
    for table, given_name, columns, remote, remote_columns in CYCLIC_FKS:
        name = given_name or connection.scalar(
            sa.text(
                "SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(:table) "
                "AND confrelid='preview_jobs'::regclass AND contype='f'"
            ),
            {"table": table},
        )
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT "{name}"')
        action = "NO ACTION" if maintenance else "RESTRICT"
        deferred = " DEFERRABLE INITIALLY DEFERRED" if maintenance or table == "import_jobs" else ""
        op.execute(
            f'ALTER TABLE {table} ADD CONSTRAINT "{name}" FOREIGN KEY ({columns}) '
            f"REFERENCES {remote} ({remote_columns}) ON DELETE {action}{deferred}"
        )


def upgrade() -> None:
    op.execute("""
        CREATE TABLE maintenance_runs (
            digest text PRIMARY KEY CHECK (digest ~ '^[0-9a-f]{64}$'),
            manifest jsonb NOT NULL,
            status text NOT NULL CHECK (status IN ('running', 'partial', 'complete', 'failed')),
            error_code text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE maintenance_batches (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            run_digest text NOT NULL REFERENCES maintenance_runs(digest),
            kind text NOT NULL CHECK (kind IN ('staging', 'product')),
            target_id uuid NOT NULL,
            counts jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_maintenance_batches_run_target
            ON maintenance_batches(run_digest, target_id);
        CREATE TABLE maintenance_authorizations (
            transaction_id text NOT NULL,
            run_digest text NOT NULL REFERENCES maintenance_runs(digest),
            kind text NOT NULL CHECK (kind IN ('staging', 'product')),
            target_id uuid NOT NULL,
            product_id uuid NOT NULL,
            table_name text NOT NULL,
            row_key jsonb NOT NULL CHECK (jsonb_typeof(row_key) = 'object'
                AND row_key <> '{}'::jsonb),
            PRIMARY KEY (transaction_id, table_name, row_key)
        );
        CREATE TABLE maintenance_schema (
            name text PRIMARY KEY,
            original_definition text NOT NULL,
            installed_definition text NOT NULL
        );
    """)
    op.execute(BLOCKED_SQL)
    connection = op.get_bind()
    cases = []
    for table, owner in OWNERS.items():
        columns = connection.execute(
            sa.text(
                "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
                "FROM pg_index i CROSS JOIN LATERAL unnest(i.indkey) key(attnum) "
                "JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=key.attnum "
                "WHERE i.indrelid=to_regclass(:table) AND i.indisprimary"
            ),
            {"table": table},
        )
        predicate = " AND ".join(f"t.{name}=(row_key->>'{name}')::{kind}" for name, kind in columns)
        cases.append(
            f"WHEN '{table}' THEN SELECT {owner} INTO result FROM {table} t WHERE {predicate};"
        )
    ownership_cases = "\n".join(cases)
    op.execute(
        "CREATE FUNCTION verboflex_maintenance_row_owner(tab text, row_key jsonb) "
        "RETURNS uuid LANGUAGE plpgsql AS $$ DECLARE result uuid; BEGIN CASE tab "
        + ownership_cases
        + " ELSE RETURN NULL; END CASE; RETURN result; END $$"
    )
    op.execute(AUTHORIZE_SQL.replace("__TABLES__", ",".join(f"'{table}'" for table in OWNERS)))
    op.execute(
        "CREATE TRIGGER maintenance_authorizations_validate BEFORE INSERT OR UPDATE "
        "ON maintenance_authorizations FOR EACH ROW "
        "EXECUTE FUNCTION verboflex_maintenance_authorize()"
    )
    op.execute(ALLOW_SQL)
    _cycle_foreign_keys(True)
    connection = op.get_bind()
    for name in GUARDS:
        original = connection.scalar(
            sa.text("SELECT pg_get_functiondef(to_regproc(:name))"), {"name": name}
        )
        if not original or original.count("BEGIN") != 1:
            raise RuntimeError("unexpected maintenance guard definition")
        modified = original.replace(
            "BEGIN",
            "BEGIN\n    IF TG_OP = 'DELETE' AND "
            "verboflex_maintenance_delete_allowed(TG_TABLE_NAME, to_jsonb(OLD)) "
            "THEN RETURN OLD; END IF;",
            1,
        )
        op.execute(modified)
        installed = connection.scalar(
            sa.text("SELECT pg_get_functiondef(to_regproc(:name))"), {"name": name}
        )
        connection.execute(
            sa.text("INSERT INTO maintenance_schema VALUES (:n, :o, :i)"),
            {"n": name, "o": original, "i": installed},
        )
    catalog = connection.scalar(sa.text(FK_CATALOG_SQL))
    connection.execute(
        sa.text("INSERT INTO maintenance_schema VALUES ('foreign_keys', :c, :c)"), {"c": catalog}
    )
    catalog = connection.scalar(sa.text(TRIGGER_CATALOG_SQL))
    connection.execute(
        sa.text("INSERT INTO maintenance_schema VALUES ('triggers', :c, :c)"), {"c": catalog}
    )
    for name in (
        "verboflex_maintenance_delete_allowed",
        "verboflex_maintenance_authorize",
        "verboflex_maintenance_product_blocked",
        "verboflex_maintenance_row_owner",
    ):
        definition = connection.scalar(
            sa.text("SELECT pg_get_functiondef(to_regproc(:n))"), {"n": name}
        )
        connection.execute(
            sa.text("INSERT INTO maintenance_schema VALUES (:n, :d, :d)"),
            {"n": name, "d": definition},
        )


def downgrade() -> None:
    connection = op.get_bind()
    for name, original, installed in connection.execute(
        sa.text("SELECT * FROM maintenance_schema")
    ):
        if name in ("foreign_keys", "triggers"):
            continue
        current = connection.scalar(
            sa.text("SELECT pg_get_functiondef(to_regproc(:name))"), {"name": name}
        )
        if current != installed:
            raise RuntimeError("maintenance guard changed; refusing unsafe downgrade")
        op.execute(original)
    _cycle_foreign_keys(False)
    op.execute("DROP FUNCTION verboflex_maintenance_delete_allowed(text, jsonb)")
    op.execute(
        "DROP TABLE maintenance_authorizations, maintenance_batches, maintenance_runs, "
        "maintenance_schema"
    )
    op.execute(
        "DROP FUNCTION verboflex_maintenance_authorize(), "
        "verboflex_maintenance_row_owner(text, jsonb), "
        "verboflex_maintenance_product_blocked(uuid)"
    )
