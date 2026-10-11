"""Add bounded worker-owned duplicate diagnostics."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0023_duplicate_reports"
down_revision = "0022_mapping_localization_root"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "duplicate_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "preview_job_id",
            sa.Uuid(),
            sa.ForeignKey("preview_jobs.id", ondelete="CASCADE"),
            unique=True,
        ),
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("import_executions.id", ondelete="CASCADE"),
            unique=True,
        ),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("issue_codes", JSONB, nullable=False),
        sa.Column("group_count", sa.Integer(), nullable=False),
        sa.Column("repeated_occurrences", sa.Integer(), nullable=False),
        sa.Column("sources", JSONB, nullable=False),
        sa.CheckConstraint(
            "(preview_job_id IS NULL) <> (execution_id IS NULL)", name="exact_owner"
        ),
    )
    op.create_table(
        "duplicate_groups",
        sa.Column(
            "report_id",
            sa.Uuid(),
            sa.ForeignKey("duplicate_reports.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("identity_digest", sa.String(64), nullable=False),
        sa.Column("repository_side", sa.String(16), nullable=False),
        sa.Column("language", sa.String(64), nullable=False),
        sa.Column("key_preview", sa.String(512), nullable=False),
        sa.Column("key_length", sa.Integer(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("report_id", "identity_digest"),
    )
    op.create_table(
        "duplicate_occurrences",
        sa.Column(
            "report_id",
            sa.Uuid(),
            sa.ForeignKey("duplicate_reports.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("group_position", sa.Integer(), primary_key=True),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("path", sa.String(4096), nullable=False),
        sa.Column("resource_position", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("duplicate_occurrences")
    op.drop_table("duplicate_groups")
    op.drop_table("duplicate_reports")
