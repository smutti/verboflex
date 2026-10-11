"""Add durable published-mapping import jobs.

Revision ID: 0012_import_jobs
Revises: 0011_active_revision_revalidations
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012_import_jobs"
down_revision: str | None = "0011_active_revision_revalidations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


IMMUTABLE_IMPORT_EXECUTION_GUARD = """
CREATE FUNCTION verboflex_guard_terminal_import_execution()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state IN ('succeeded', 'failed') THEN
        RAISE EXCEPTION 'terminal import execution is immutable'
            USING ERRCODE = '55000';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$
"""


IMPORT_SOURCE_REFERENCE_GUARD = """
CREATE FUNCTION verboflex_guard_import_source_reference()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    execution_state text;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT state INTO execution_state
        FROM import_executions
        WHERE id = OLD.execution_id;

        IF execution_state IN ('succeeded', 'failed') THEN
            RAISE EXCEPTION 'terminal import source reference is immutable'
                USING ERRCODE = '55000';
        END IF;
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM import_executions AS execution
        JOIN import_jobs AS job ON job.id = execution.import_job_id
        JOIN product_mapping_repository_sides AS side
          ON side.mapping_id = job.mapping_id
         AND side.role = NEW.repository_side
         AND side.repository_id = NEW.repository_id
         AND side.source_branch = NEW.source_branch
        WHERE execution.id = NEW.execution_id
    ) THEN
        RAISE EXCEPTION 'import source reference ownership violation'
            USING ERRCODE = '23503';
    END IF;

    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    """Create logical imports, executions, and metadata-only source references."""
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mapping_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topology", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("current_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "active_baseline_execution_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_category", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.String(length=256), nullable=True),
        sa.Column("latest_execution_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('queued', 'running', 'current', 'import_failed')",
            name=op.f("ck_import_jobs_state_value"),
        ),
        sa.CheckConstraint(
            "topology IN ('direct', 'separate')",
            name=op.f("ck_import_jobs_topology_value"),
        ),
        sa.CheckConstraint(
            "retry_count >= 0",
            name=op.f("ck_import_jobs_retry_count_non_negative"),
        ),
        sa.CheckConstraint(
            "(state IN ('queued', 'running', 'current') "
            "AND error_category IS NULL AND error_message IS NULL) OR "
            "(state = 'import_failed' AND error_category IS NOT NULL "
            "AND error_message IS NOT NULL)",
            name=op.f("ck_import_jobs_state_error_payload"),
        ),
        sa.CheckConstraint(
            "state <> 'current' OR active_baseline_execution_id IS NOT NULL",
            name=op.f("ck_import_jobs_current_requires_baseline"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            name="fk_import_jobs_owned_revision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id", "mapping_id"],
            ["product_repository_mappings.revision_id", "product_repository_mappings.id"],
            name="fk_import_jobs_owned_mapping",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_jobs")),
        sa.UniqueConstraint("mapping_id", name="uq_import_jobs_mapping"),
    )
    op.create_index(op.f("ix_import_jobs_product_id"), "import_jobs", ["product_id"])
    op.create_index(op.f("ix_import_jobs_revision_id"), "import_jobs", ["revision_id"])
    op.create_index(
        "ix_import_jobs_revision_mapping",
        "import_jobs",
        ["revision_id", "mapping_id"],
    )

    op.create_table(
        "import_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("connection_generation", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed')",
            name=op.f("ck_import_executions_state_value"),
        ),
        sa.CheckConstraint(
            "sequence > 0",
            name=op.f("ck_import_executions_positive_sequence"),
        ),
        sa.CheckConstraint(
            "connection_generation >= 0",
            name=op.f("ck_import_executions_connection_generation_non_negative"),
        ),
        sa.CheckConstraint(
            "(state = 'queued' AND started_at IS NULL AND finished_at IS NULL) OR "
            "(state = 'running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
            "(state IN ('succeeded', 'failed') AND started_at IS NOT NULL "
            "AND finished_at IS NOT NULL)",
            name=op.f("ck_import_executions_state_timestamps"),
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name=op.f("fk_import_executions_import_job_id_import_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_executions")),
        sa.UniqueConstraint(
            "id",
            "import_job_id",
            name="uq_import_executions_id_job",
        ),
        sa.UniqueConstraint(
            "import_job_id",
            "sequence",
            name="uq_import_executions_job_sequence",
        ),
    )
    op.create_index(
        "ix_import_executions_job_sequence",
        "import_executions",
        ["import_job_id", "sequence"],
    )
    op.create_foreign_key(
        "fk_import_jobs_current_execution",
        "import_jobs",
        "import_executions",
        ["current_execution_id", "id"],
        ["id", "import_job_id"],
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_import_jobs_active_baseline",
        "import_jobs",
        "import_executions",
        ["active_baseline_execution_id", "id"],
        ["id", "import_job_id"],
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )

    op.create_table(
        "import_source_references",
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("repository_side", sa.String(length=16), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_branch", sa.String(length=255), nullable=False),
        sa.Column("commit_hash", sa.String(length=40), nullable=False),
        sa.Column("path", sa.String(length=4096), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "position >= 0",
            name=op.f("ck_import_source_references_position_non_negative"),
        ),
        sa.CheckConstraint(
            "repository_side IN ('direct', 'keys', 'translations')",
            name=op.f("ck_import_source_references_repository_side_value"),
        ),
        sa.CheckConstraint(
            "char_length(source_branch) BETWEEN 1 AND 255",
            name=op.f("ck_import_source_references_source_branch_length"),
        ),
        sa.CheckConstraint(
            "char_length(commit_hash) = 40 AND commit_hash ~ '^[0-9a-f]{40}$'",
            name=op.f("ck_import_source_references_commit_hash_sha1"),
        ),
        sa.CheckConstraint(
            "char_length(path) BETWEEN 1 AND 4096",
            name=op.f("ck_import_source_references_path_length"),
        ),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name=op.f("ck_import_source_references_size_non_negative"),
        ),
        sa.CheckConstraint(
            "char_length(sha256) = 64 AND sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_import_source_references_sha256_digest"),
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["import_executions.id"],
            name=op.f("fk_import_source_references_execution_id_import_executions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_import_source_references_repository_id_repositories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "execution_id",
            "position",
            name=op.f("pk_import_source_references"),
        ),
        sa.UniqueConstraint(
            "execution_id",
            "repository_side",
            "path",
            name="uq_import_source_references_side_path",
        ),
    )
    op.create_index(
        "ix_import_source_references_execution_side_position",
        "import_source_references",
        ["execution_id", "repository_side", "position"],
    )
    op.execute(IMMUTABLE_IMPORT_EXECUTION_GUARD)
    op.execute(
        "CREATE TRIGGER trg_import_executions_terminal_immutable "
        "BEFORE UPDATE OR DELETE ON import_executions "
        "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_terminal_import_execution()"
    )
    op.execute(IMPORT_SOURCE_REFERENCE_GUARD)
    op.execute(
        "CREATE TRIGGER trg_import_source_references_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON import_source_references "
        "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_import_source_reference()"
    )


def downgrade() -> None:
    """Remove only the import persistence introduced by this revision."""
    op.execute("DROP TRIGGER trg_import_source_references_guard ON import_source_references")
    op.execute("DROP FUNCTION verboflex_guard_import_source_reference()")
    op.execute("DROP TRIGGER trg_import_executions_terminal_immutable ON import_executions")
    op.execute("DROP FUNCTION verboflex_guard_terminal_import_execution()")
    op.drop_index(
        "ix_import_source_references_execution_side_position",
        table_name="import_source_references",
    )
    op.drop_table("import_source_references")
    op.drop_constraint(
        "fk_import_jobs_active_baseline",
        "import_jobs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_import_jobs_current_execution",
        "import_jobs",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_import_executions_job_sequence",
        table_name="import_executions",
    )
    op.drop_table("import_executions")
    op.drop_index("ix_import_jobs_revision_mapping", table_name="import_jobs")
    op.drop_index(op.f("ix_import_jobs_revision_id"), table_name="import_jobs")
    op.drop_index(op.f("ix_import_jobs_product_id"), table_name="import_jobs")
    op.drop_table("import_jobs")
