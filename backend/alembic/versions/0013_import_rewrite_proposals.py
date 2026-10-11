"""Add complete mapping-scoped import rewrite proposals.

Revision ID: 0013_import_rewrite_proposals
Revises: 0012_import_jobs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_import_rewrite_proposals"
down_revision: str | None = "0012_import_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PROPOSAL_GUARD = """
CREATE FUNCTION verboflex_guard_import_rewrite_proposal()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'import rewrite proposal is immutable'
            USING ERRCODE = '55000';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF ROW(
            NEW.id, NEW.import_job_id, NEW.product_id, NEW.revision_id,
            NEW.revision_version, NEW.mapping_id, NEW.topology,
            NEW.connection_generation, NEW.proposed_execution_id,
            NEW.old_baseline_execution_id, NEW.direct_repository_id,
            NEW.direct_old_commit_hash, NEW.direct_new_commit_hash,
            NEW.keys_repository_id, NEW.keys_old_commit_hash,
            NEW.keys_new_commit_hash, NEW.translations_repository_id,
            NEW.translations_old_commit_hash, NEW.translations_new_commit_hash,
            NEW.complete, NEW.digest, NEW.created_at
        ) IS DISTINCT FROM ROW(
            OLD.id, OLD.import_job_id, OLD.product_id, OLD.revision_id,
            OLD.revision_version, OLD.mapping_id, OLD.topology,
            OLD.connection_generation, OLD.proposed_execution_id,
            OLD.old_baseline_execution_id, OLD.direct_repository_id,
            OLD.direct_old_commit_hash, OLD.direct_new_commit_hash,
            OLD.keys_repository_id, OLD.keys_old_commit_hash,
            OLD.keys_new_commit_hash, OLD.translations_repository_id,
            OLD.translations_old_commit_hash, OLD.translations_new_commit_hash,
            OLD.complete, OLD.digest, OLD.created_at
        ) OR OLD.status <> 'pending'
           OR NEW.status NOT IN ('confirmed', 'superseded') THEN
            RAISE EXCEPTION 'import rewrite proposal identity is immutable'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM import_jobs AS job
        JOIN products AS product
          ON product.id = job.product_id
         AND product.is_active
         AND product.active_revision_id = job.revision_id
        JOIN product_revisions AS revision
          ON revision.id = job.revision_id
         AND revision.product_id = job.product_id
         AND revision.is_published
        JOIN product_repository_mappings AS mapping
          ON mapping.id = job.mapping_id
         AND mapping.revision_id = job.revision_id
        JOIN import_executions AS proposed
          ON proposed.id = job.current_execution_id
         AND proposed.import_job_id = job.id
         AND proposed.state = 'succeeded'
        JOIN import_executions AS baseline
          ON baseline.id = job.active_baseline_execution_id
         AND baseline.import_job_id = job.id
         AND baseline.state = 'succeeded'
        WHERE job.id = NEW.import_job_id
          AND job.state = 'current'
          AND job.product_id = NEW.product_id
          AND job.revision_id = NEW.revision_id
          AND job.mapping_id = NEW.mapping_id
          AND job.topology = NEW.topology
          AND revision.version = NEW.revision_version
          AND proposed.id = NEW.proposed_execution_id
          AND proposed.connection_generation = NEW.connection_generation
          AND baseline.id = NEW.old_baseline_execution_id
    ) THEN
        RAISE EXCEPTION 'import rewrite proposal currentness violation'
            USING ERRCODE = '23503';
    END IF;

    IF NEW.topology = 'direct' THEN
        IF NEW.direct_old_commit_hash = NEW.direct_new_commit_hash OR NOT EXISTS (
            SELECT 1
            FROM product_mapping_repository_sides AS side
            WHERE side.mapping_id = NEW.mapping_id
              AND side.role = 'direct'
              AND side.repository_id = NEW.direct_repository_id
        ) OR NOT EXISTS (
            SELECT 1 FROM import_source_references
            WHERE execution_id = NEW.old_baseline_execution_id
              AND repository_side = 'direct'
              AND repository_id = NEW.direct_repository_id
              AND commit_hash = NEW.direct_old_commit_hash
        ) OR NOT EXISTS (
            SELECT 1 FROM import_source_references
            WHERE execution_id = NEW.proposed_execution_id
              AND repository_side = 'direct'
              AND repository_id = NEW.direct_repository_id
              AND commit_hash = NEW.direct_new_commit_hash
        ) THEN
            RAISE EXCEPTION 'import rewrite proposal source ownership violation'
                USING ERRCODE = '23503';
        END IF;
    ELSE
        IF (
            NEW.keys_old_commit_hash = NEW.keys_new_commit_hash
            AND NEW.translations_old_commit_hash = NEW.translations_new_commit_hash
        ) OR NOT EXISTS (
            SELECT 1 FROM product_mapping_repository_sides AS side
            WHERE side.mapping_id = NEW.mapping_id
              AND side.role = 'keys'
              AND side.repository_id = NEW.keys_repository_id
        ) OR NOT EXISTS (
            SELECT 1 FROM product_mapping_repository_sides AS side
            WHERE side.mapping_id = NEW.mapping_id
              AND side.role = 'translations'
              AND side.repository_id = NEW.translations_repository_id
        ) OR NOT EXISTS (
            SELECT 1 FROM import_source_references
            WHERE execution_id = NEW.old_baseline_execution_id
              AND repository_side = 'keys'
              AND repository_id = NEW.keys_repository_id
              AND commit_hash = NEW.keys_old_commit_hash
        ) OR NOT EXISTS (
            SELECT 1 FROM import_source_references
            WHERE execution_id = NEW.proposed_execution_id
              AND repository_side = 'keys'
              AND repository_id = NEW.keys_repository_id
              AND commit_hash = NEW.keys_new_commit_hash
        ) OR NOT EXISTS (
            SELECT 1 FROM import_source_references
            WHERE execution_id = NEW.old_baseline_execution_id
              AND repository_side = 'translations'
              AND repository_id = NEW.translations_repository_id
              AND commit_hash = NEW.translations_old_commit_hash
        ) OR NOT EXISTS (
            SELECT 1 FROM import_source_references
            WHERE execution_id = NEW.proposed_execution_id
              AND repository_side = 'translations'
              AND repository_id = NEW.translations_repository_id
              AND commit_hash = NEW.translations_new_commit_hash
        ) THEN
            RAISE EXCEPTION 'import rewrite proposal source ownership violation'
                USING ERRCODE = '23503';
        END IF;
    END IF;

    RETURN NEW;
END;
$$
"""


DELTA_GUARD = """
CREATE FUNCTION verboflex_guard_import_rewrite_delta()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    proposal_topology text;
    proposal_status text;
    expected_position integer;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        RAISE EXCEPTION 'import rewrite delta is immutable'
            USING ERRCODE = '55000';
    END IF;

    SELECT topology, status INTO proposal_topology, proposal_status
    FROM import_rewrite_proposals
    WHERE id = NEW.proposal_id;

    SELECT count(*) INTO expected_position
    FROM import_rewrite_deltas
    WHERE proposal_id = NEW.proposal_id;

    IF proposal_status <> 'pending'
       OR NEW.position <> expected_position
       OR (proposal_topology = 'direct' AND NEW.repository_side <> 'direct')
       OR (proposal_topology = 'separate'
           AND NEW.repository_side NOT IN ('keys', 'translations'))
       OR (proposal_topology = 'separate'
           AND NEW.repository_side = 'keys'
           AND EXISTS (
               SELECT 1 FROM import_rewrite_deltas
               WHERE proposal_id = NEW.proposal_id
                 AND repository_side = 'translations'
           )) THEN
        RAISE EXCEPTION 'import rewrite delta order or ownership violation'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$
"""


def _commit_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("direct_repository_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direct_old_commit_hash", sa.String(length=40), nullable=True),
        sa.Column("direct_new_commit_hash", sa.String(length=40), nullable=True),
        sa.Column("keys_repository_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("keys_old_commit_hash", sa.String(length=40), nullable=True),
        sa.Column("keys_new_commit_hash", sa.String(length=40), nullable=True),
        sa.Column("translations_repository_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("translations_old_commit_hash", sa.String(length=40), nullable=True),
        sa.Column("translations_new_commit_hash", sa.String(length=40), nullable=True),
    ]


def upgrade() -> None:
    """Create durable complete proposal authority and ordered metadata deltas."""
    op.create_table(
        "import_rewrite_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_version", sa.Integer(), nullable=False),
        sa.Column("mapping_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topology", sa.String(length=16), nullable=False),
        sa.Column("connection_generation", sa.Integer(), nullable=False),
        sa.Column("proposed_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("old_baseline_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        *_commit_columns(),
        sa.Column("complete", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision_version > 0",
            name=op.f("ck_import_rewrite_proposals_positive_revision_version"),
        ),
        sa.CheckConstraint(
            "connection_generation >= 0",
            name=op.f("ck_import_rewrite_proposals_connection_generation_non_negative"),
        ),
        sa.CheckConstraint(
            "topology IN ('direct', 'separate')",
            name=op.f("ck_import_rewrite_proposals_topology_value"),
        ),
        sa.CheckConstraint(
            "complete",
            name=op.f("ck_import_rewrite_proposals_complete_authority"),
        ),
        sa.CheckConstraint(
            "char_length(digest) = 64 AND digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_import_rewrite_proposals_digest_sha256"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'superseded')",
            name=op.f("ck_import_rewrite_proposals_status_value"),
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND resolved_at IS NULL AND confirmed_by IS NULL) OR "
            "(status = 'superseded' AND resolved_at IS NOT NULL "
            "AND confirmed_by IS NULL) OR "
            "(status = 'confirmed' AND resolved_at IS NOT NULL "
            "AND confirmed_by IS NOT NULL)",
            name=op.f("ck_import_rewrite_proposals_status_payload"),
        ),
        sa.CheckConstraint(
            "(topology = 'direct' AND direct_repository_id IS NOT NULL "
            "AND direct_old_commit_hash IS NOT NULL "
            "AND direct_new_commit_hash IS NOT NULL "
            "AND keys_repository_id IS NULL AND keys_old_commit_hash IS NULL "
            "AND keys_new_commit_hash IS NULL "
            "AND translations_repository_id IS NULL "
            "AND translations_old_commit_hash IS NULL "
            "AND translations_new_commit_hash IS NULL) OR "
            "(topology = 'separate' AND direct_repository_id IS NULL "
            "AND direct_old_commit_hash IS NULL AND direct_new_commit_hash IS NULL "
            "AND keys_repository_id IS NOT NULL "
            "AND keys_old_commit_hash IS NOT NULL "
            "AND keys_new_commit_hash IS NOT NULL "
            "AND translations_repository_id IS NOT NULL "
            "AND translations_old_commit_hash IS NOT NULL "
            "AND translations_new_commit_hash IS NOT NULL)",
            name=op.f("ck_import_rewrite_proposals_topology_commits"),
        ),
        sa.CheckConstraint(
            "(direct_old_commit_hash IS NULL OR (char_length(direct_old_commit_hash) = 40 "
            "AND direct_old_commit_hash ~ '^[0-9a-f]{40}$')) AND "
            "(direct_new_commit_hash IS NULL OR (char_length(direct_new_commit_hash) = 40 "
            "AND direct_new_commit_hash ~ '^[0-9a-f]{40}$')) AND "
            "(keys_old_commit_hash IS NULL OR (char_length(keys_old_commit_hash) = 40 "
            "AND keys_old_commit_hash ~ '^[0-9a-f]{40}$')) AND "
            "(keys_new_commit_hash IS NULL OR (char_length(keys_new_commit_hash) = 40 "
            "AND keys_new_commit_hash ~ '^[0-9a-f]{40}$')) AND "
            "(translations_old_commit_hash IS NULL OR "
            "(char_length(translations_old_commit_hash) = 40 "
            "AND translations_old_commit_hash ~ '^[0-9a-f]{40}$')) AND "
            "(translations_new_commit_hash IS NULL OR "
            "(char_length(translations_new_commit_hash) = 40 "
            "AND translations_new_commit_hash ~ '^[0-9a-f]{40}$'))",
            name=op.f("ck_import_rewrite_proposals_commit_hashes_sha1"),
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name=op.f("fk_import_rewrite_proposals_import_job_id_import_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            name="fk_import_rewrite_proposals_owned_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id", "mapping_id"],
            ["product_repository_mappings.revision_id", "product_repository_mappings.id"],
            name="fk_import_rewrite_proposals_owned_mapping",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["old_baseline_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_import_rewrite_proposals_old_baseline",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["proposed_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_import_rewrite_proposals_proposed_execution",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["direct_repository_id"],
            ["repositories.id"],
            name=op.f("fk_import_rewrite_proposals_direct_repository_id_repositories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["keys_repository_id"],
            ["repositories.id"],
            name=op.f("fk_import_rewrite_proposals_keys_repository_id_repositories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["translations_repository_id"],
            ["repositories.id"],
            name=op.f("fk_import_rewrite_proposals_translations_repository_id_repositories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by"],
            ["users.id"],
            name=op.f("fk_import_rewrite_proposals_confirmed_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_rewrite_proposals")),
    )
    op.create_index(
        "uq_import_rewrite_proposals_pending_job",
        "import_rewrite_proposals",
        ["import_job_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_import_rewrite_proposals_mapping_status",
        "import_rewrite_proposals",
        ["mapping_id", "status"],
    )

    op.create_table(
        "import_rewrite_deltas",
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("repository_side", sa.String(length=16), nullable=False),
        sa.Column("change", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=4096), nullable=False),
        sa.CheckConstraint(
            "position >= 0",
            name=op.f("ck_import_rewrite_deltas_position_non_negative"),
        ),
        sa.CheckConstraint(
            "repository_side IN ('direct', 'keys', 'translations')",
            name=op.f("ck_import_rewrite_deltas_repository_side_value"),
        ),
        sa.CheckConstraint(
            "change IN ('added', 'modified', 'removed')",
            name=op.f("ck_import_rewrite_deltas_change_value"),
        ),
        sa.CheckConstraint(
            "char_length(path) BETWEEN 1 AND 4096",
            name=op.f("ck_import_rewrite_deltas_path_length"),
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["import_rewrite_proposals.id"],
            name=op.f("fk_import_rewrite_deltas_proposal_id_import_rewrite_proposals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("proposal_id", "position", name=op.f("pk_import_rewrite_deltas")),
        sa.UniqueConstraint(
            "proposal_id",
            "repository_side",
            "path",
            name="uq_import_rewrite_deltas_side_path",
        ),
    )
    op.execute(PROPOSAL_GUARD)
    op.execute(
        "CREATE TRIGGER trg_import_rewrite_proposals_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON import_rewrite_proposals "
        "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_import_rewrite_proposal()"
    )
    op.execute(DELTA_GUARD)
    op.execute(
        "CREATE TRIGGER trg_import_rewrite_deltas_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON import_rewrite_deltas "
        "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_import_rewrite_delta()"
    )


def downgrade() -> None:
    """Remove only rewrite proposal authority introduced by this revision."""
    op.execute("DROP TRIGGER trg_import_rewrite_deltas_guard ON import_rewrite_deltas")
    op.execute("DROP FUNCTION verboflex_guard_import_rewrite_delta()")
    op.execute("DROP TRIGGER trg_import_rewrite_proposals_guard ON import_rewrite_proposals")
    op.execute("DROP FUNCTION verboflex_guard_import_rewrite_proposal()")
    op.drop_table("import_rewrite_deltas")
    op.drop_index(
        "ix_import_rewrite_proposals_mapping_status",
        table_name="import_rewrite_proposals",
    )
    op.drop_index(
        "uq_import_rewrite_proposals_pending_job",
        table_name="import_rewrite_proposals",
    )
    op.drop_table("import_rewrite_proposals")
