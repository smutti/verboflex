"""Bind explicit preview confirmations to revision-owned mappings.

Revision ID: 0007_preview_confirmations
Revises: 0006_preview_jobs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_preview_confirmations"
down_revision: str | None = "0006_preview_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add one all-or-none historical confirmation reference per mapping."""
    op.add_column(
        "product_repository_mappings",
        sa.Column("confirmed_preview_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "product_repository_mappings",
        sa.Column("confirmed_preview_digest", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "product_repository_mappings",
        sa.Column("preview_confirmed_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "product_repository_mappings",
        sa.Column("preview_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_product_repository_mappings_preview_confirmation_state"),
        "product_repository_mappings",
        "(confirmed_preview_job_id IS NULL AND confirmed_preview_digest IS NULL "
        "AND preview_confirmed_by IS NULL AND preview_confirmed_at IS NULL) OR "
        "(confirmed_preview_job_id IS NOT NULL "
        "AND char_length(confirmed_preview_digest) = 64 "
        "AND confirmed_preview_digest ~ '^[0-9a-f]{64}$' "
        "AND preview_confirmed_by IS NOT NULL AND preview_confirmed_at IS NOT NULL)",
    )
    op.create_foreign_key(
        op.f("fk_product_repository_mappings_confirmed_preview_job_id_preview_jobs"),
        "product_repository_mappings",
        "preview_jobs",
        ["confirmed_preview_job_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_product_repository_mappings_preview_confirmed_by_users"),
        "product_repository_mappings",
        "users",
        ["preview_confirmed_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_product_repository_mappings_confirmed_preview_job",
        "product_repository_mappings",
        ["confirmed_preview_job_id"],
    )


def downgrade() -> None:
    """Remove confirmation authority without altering preview history."""
    op.drop_constraint(
        "uq_product_repository_mappings_confirmed_preview_job",
        "product_repository_mappings",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_product_repository_mappings_preview_confirmed_by_users"),
        "product_repository_mappings",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_product_repository_mappings_confirmed_preview_job_id_preview_jobs"),
        "product_repository_mappings",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("ck_product_repository_mappings_preview_confirmation_state"),
        "product_repository_mappings",
        type_="check",
    )
    op.drop_column("product_repository_mappings", "preview_confirmed_at")
    op.drop_column("product_repository_mappings", "preview_confirmed_by")
    op.drop_column("product_repository_mappings", "confirmed_preview_digest")
    op.drop_column("product_repository_mappings", "confirmed_preview_job_id")
