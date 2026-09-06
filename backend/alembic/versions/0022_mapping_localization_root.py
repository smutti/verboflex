"""Persist an optional discovery root on each immutable mapping side."""

import sqlalchemy as sa

from alembic import op

revision = "0022_mapping_localization_root"
down_revision = "0021_retained_constraint_epoch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_mapping_repository_sides",
        sa.Column("localization_root", sa.String(4096), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product_mapping_repository_sides", "localization_root")
