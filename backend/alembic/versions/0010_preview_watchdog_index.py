"""Add the stale-running preview watchdog index.

Revision ID: 0010_preview_watchdog_index
Revises: 0009_product_graph_integrity
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_preview_watchdog_index"
down_revision: str | None = "0009_product_graph_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the running-only age access path used by the bounded watchdog."""
    op.create_index(
        "ix_preview_jobs_watchdog_state_started_at",
        "preview_jobs",
        ["state", "started_at"],
        unique=False,
        postgresql_where=sa.text("state = 'running'"),
    )


def downgrade() -> None:
    """Remove only the preview watchdog access path."""
    op.drop_index(
        "ix_preview_jobs_watchdog_state_started_at",
        table_name="preview_jobs",
    )
