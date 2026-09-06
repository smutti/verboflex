"""Add one bounded safe preview failure diagnostic."""

import sqlalchemy as sa

from alembic import op

revision = "0025_preview_diagnostics"
down_revision = "0024_product_logical_deletion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "preview_jobs",
        sa.Column("diagnostic_code", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_preview_jobs_diagnostic_code_value",
        "preview_jobs",
        "diagnostic_code IS NULL OR diagnostic_code = 'repository_scan_limit_reached'",
    )
    op.create_check_constraint(
        "ck_preview_jobs_diagnostic_failure_only",
        "preview_jobs",
        "diagnostic_code IS NULL OR (state = 'failed' AND error_code = 'processing_failed')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_preview_jobs_diagnostic_failure_only",
        "preview_jobs",
        type_="check",
    )
    op.drop_constraint(
        "ck_preview_jobs_diagnostic_code_value",
        "preview_jobs",
        type_="check",
    )
    op.drop_column("preview_jobs", "diagnostic_code")
