"""Durable catalog refresh after a verified working-branch commit."""

import sqlalchemy as sa

from alembic import op

revision = "0060_branch_catalog_refresh"
down_revision = "0059_authoring_bulk_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("branch_jobs", sa.Column("catalog_refresh_state", sa.String(16)))
    # Executions can be removed with an old product revision. Keep the historical
    # receipt without extending the lifecycle of that revision.
    op.add_column("branch_jobs", sa.Column("catalog_refresh_execution_id", sa.UUID()))
    op.create_check_constraint(
        "catalog_refresh_state",
        "branch_jobs",
        "catalog_refresh_state IS NULL OR catalog_refresh_state IN "
        "('pending','running','succeeded','failed','skipped')",
    )
    op.create_index(
        "ix_branch_jobs_catalog_refresh",
        "branch_jobs",
        ["workflow_id"],
        postgresql_where=sa.text("catalog_refresh_state IN ('pending','running')"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM branch_jobs "
            "WHERE catalog_refresh_state IN ('pending','running'))"
        )
    ):
        raise RuntimeError("Wait for pending catalog refreshes before downgrade")
    op.drop_index("ix_branch_jobs_catalog_refresh", table_name="branch_jobs")
    op.drop_constraint(op.f("ck_branch_jobs_catalog_refresh_state"), "branch_jobs", type_="check")
    op.drop_column("branch_jobs", "catalog_refresh_execution_id")
    op.drop_column("branch_jobs", "catalog_refresh_state")
