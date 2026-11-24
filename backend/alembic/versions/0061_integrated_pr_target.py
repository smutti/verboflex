"""Keep the verified destination of a satisfied duplicate publication request."""

import sqlalchemy as sa

from alembic import op

revision = "0061_integrated_pr_target"
down_revision = "0060_branch_catalog_refresh"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("branch_jobs", sa.Column("integrated_target_hash", sa.String(40)))


def downgrade() -> None:
    op.drop_column("branch_jobs", "integrated_target_hash")
