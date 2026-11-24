"""Persist Bitbucket publication retry deadlines across worker restarts."""

import sqlalchemy as sa

from alembic import op

revision = "0062_branch_rate_limit"
down_revision = "0061_integrated_pr_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("branch_jobs", sa.Column("retry_at", sa.DateTime(timezone=True)))
    op.add_column(
        "branch_jobs",
        sa.Column("rate_limit_attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("branch_jobs", "rate_limit_attempts")
    op.drop_column("branch_jobs", "retry_at")
