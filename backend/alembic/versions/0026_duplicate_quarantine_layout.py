"""Retain private layout authority for duplicate quarantine reconciliation."""

import sqlalchemy as sa

from alembic import op

revision = "0026_duplicate_quarantine_layout"
down_revision = "0025_preview_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "duplicate_groups",
        sa.Column("layout_identity", sa.String(length=4096), nullable=True),
    )
    op.execute(
        "UPDATE duplicate_groups SET layout_identity = '<legacy-unavailable>' "
        "WHERE layout_identity IS NULL"
    )
    op.alter_column("duplicate_groups", "layout_identity", nullable=False)


def downgrade() -> None:
    op.drop_column("duplicate_groups", "layout_identity")
