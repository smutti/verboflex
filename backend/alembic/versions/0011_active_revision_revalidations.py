"""Add immutable active-revision revalidation authority.

Revision ID: 0011_active_revision_revalidations
Revises: 0010_preview_watchdog_index
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_active_revision_revalidations"
down_revision: str | None = "0010_preview_watchdog_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


IMMUTABLE_CONFIRMATION_GUARD = """
CREATE FUNCTION verboflex_guard_active_revalidation_confirmation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'active revision revalidation confirmation is immutable'
        USING ERRCODE = '55000';
END;
$$
"""


def upgrade() -> None:
    """Backfill candidate scope and add exact published-revision sidecar authority."""
    op.add_column(
        "preview_jobs",
        sa.Column(
            "revision_scope",
            sa.String(length=24),
            server_default="candidate",
            nullable=True,
        ),
    )
    op.execute("UPDATE preview_jobs SET revision_scope = 'candidate'")
    op.alter_column(
        "preview_jobs",
        "revision_scope",
        existing_type=sa.String(length=24),
        nullable=False,
        server_default="candidate",
    )
    op.create_check_constraint(
        op.f("ck_preview_jobs_revision_scope_value"),
        "preview_jobs",
        "revision_scope IN ('candidate', 'active_revalidation')",
    )
    op.create_unique_constraint(
        "uq_preview_jobs_id_revision_scope",
        "preview_jobs",
        ["id", "revision_scope"],
    )

    op.create_table(
        "active_revision_revalidation_confirmations",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "revision_scope",
            sa.String(length=24),
            server_default="active_revalidation",
            nullable=False,
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_version", sa.Integer(), nullable=False),
        sa.Column("mapping_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_generation", sa.Integer(), nullable=False),
        sa.Column("preview_digest", sa.String(length=64), nullable=False),
        sa.Column("layout_candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("layout_candidate_version", sa.Integer(), nullable=False),
        sa.Column("confirmed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision_scope = 'active_revalidation'",
            name=op.f("ck_active_revision_revalidation_confirmations_revision_scope_value"),
        ),
        sa.CheckConstraint(
            "revision_version > 0",
            name=op.f("ck_active_revision_revalidation_confirmations_positive_revision_version"),
        ),
        sa.CheckConstraint(
            "connection_generation >= 0",
            name=op.f(
                "ck_active_revision_revalidation_confirmations_connection_generation_non_negative"
            ),
        ),
        sa.CheckConstraint(
            "char_length(preview_digest) = 64 AND preview_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_active_revision_revalidation_confirmations_preview_digest_sha256"),
        ),
        sa.CheckConstraint(
            "layout_candidate_version > 0",
            name=op.f(
                "ck_active_revision_revalidation_confirmations_positive_layout_candidate_version"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "revision_scope"],
            ["preview_jobs.id", "preview_jobs.revision_scope"],
            name="fk_active_revalidation_confirmation_job_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            name="fk_active_revalidation_confirmation_owned_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id", "mapping_id"],
            [
                "product_repository_mappings.revision_id",
                "product_repository_mappings.id",
            ],
            name="fk_active_revalidation_confirmation_owned_mapping",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by"],
            ["users.id"],
            name="fk_active_revalidation_confirmation_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "job_id",
            name=op.f("pk_active_revision_revalidation_confirmations"),
        ),
    )
    op.create_index(
        op.f("ix_active_revision_revalidation_confirmations_product_id"),
        "active_revision_revalidation_confirmations",
        ["product_id"],
    )
    op.create_index(
        op.f("ix_active_revision_revalidation_confirmations_revision_id"),
        "active_revision_revalidation_confirmations",
        ["revision_id"],
    )
    op.create_index(
        op.f("ix_active_revision_revalidation_confirmations_mapping_id"),
        "active_revision_revalidation_confirmations",
        ["mapping_id"],
    )
    op.execute(IMMUTABLE_CONFIRMATION_GUARD)
    op.execute(
        "CREATE TRIGGER trg_active_revalidation_confirmations_immutable "
        "BEFORE UPDATE OR DELETE ON active_revision_revalidation_confirmations "
        "FOR EACH ROW EXECUTE FUNCTION "
        "verboflex_guard_active_revalidation_confirmation()"
    )


def downgrade() -> None:
    """Remove only the sidecar and scope objects owned by this revision."""
    op.execute(
        "DROP TRIGGER trg_active_revalidation_confirmations_immutable "
        "ON active_revision_revalidation_confirmations"
    )
    op.execute("DROP FUNCTION verboflex_guard_active_revalidation_confirmation()")
    op.drop_index(
        op.f("ix_active_revision_revalidation_confirmations_mapping_id"),
        table_name="active_revision_revalidation_confirmations",
    )
    op.drop_index(
        op.f("ix_active_revision_revalidation_confirmations_revision_id"),
        table_name="active_revision_revalidation_confirmations",
    )
    op.drop_index(
        op.f("ix_active_revision_revalidation_confirmations_product_id"),
        table_name="active_revision_revalidation_confirmations",
    )
    op.drop_table("active_revision_revalidation_confirmations")
    op.drop_constraint(
        "uq_preview_jobs_id_revision_scope",
        "preview_jobs",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_preview_jobs_revision_scope_value"),
        "preview_jobs",
        type_="check",
    )
    op.drop_column("preview_jobs", "revision_scope")
