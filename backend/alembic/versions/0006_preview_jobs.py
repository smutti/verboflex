"""Create durable preview jobs.

Revision ID: 0006_preview_jobs
Revises: 0005_product_mappings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_preview_jobs"
down_revision: str | None = "0005_product_mappings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create complete preview identity and bounded attempt state."""
    op.create_table(
        "preview_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_revision_version", sa.Integer(), nullable=False),
        sa.Column("mapping_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topology", sa.String(length=16), nullable=False),
        sa.Column("connection_generation", sa.Integer(), nullable=False),
        sa.Column("detector_version", sa.String(length=64), nullable=False),
        sa.Column("layout_identity", sa.String(length=128), nullable=False),
        sa.Column("repository_sides", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', 'timed_out')",
            name=op.f("ck_preview_jobs_state_value"),
        ),
        sa.CheckConstraint("attempt > 0", name=op.f("ck_preview_jobs_positive_attempt")),
        sa.CheckConstraint(
            "candidate_revision_version > 0",
            name=op.f("ck_preview_jobs_positive_candidate_revision_version"),
        ),
        sa.CheckConstraint(
            "connection_generation >= 0",
            name=op.f("ck_preview_jobs_connection_generation_non_negative"),
        ),
        sa.CheckConstraint(
            "char_length(input_digest) = 64 AND input_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_preview_jobs_input_digest_sha256"),
        ),
        sa.CheckConstraint(
            "char_length(detector_version) BETWEEN 1 AND 64",
            name=op.f("ck_preview_jobs_detector_version_length"),
        ),
        sa.CheckConstraint(
            "char_length(layout_identity) BETWEEN 1 AND 128",
            name=op.f("ck_preview_jobs_layout_identity_length"),
        ),
        sa.CheckConstraint(
            "(state = 'queued' AND started_at IS NULL AND finished_at IS NULL "
            "AND result IS NULL AND error_code IS NULL) OR "
            "(state = 'running' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND result IS NULL AND error_code IS NULL) OR "
            "(state = 'succeeded' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND result IS NOT NULL AND error_code IS NULL) OR "
            "(state IN ('failed', 'timed_out') AND finished_at IS NOT NULL "
            "AND result IS NULL AND error_code IS NOT NULL)",
            name=op.f("ck_preview_jobs_state_payload"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_preview_jobs_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_revision_id"],
            ["product_revisions.id"],
            name=op.f("fk_preview_jobs_candidate_revision_id_product_revisions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mapping_id"],
            ["product_repository_mappings.id"],
            name=op.f("fk_preview_jobs_mapping_id_product_repository_mappings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_preview_jobs")),
        sa.UniqueConstraint(
            "input_digest",
            "attempt",
            name="uq_preview_jobs_digest_attempt",
        ),
    )
    op.create_index(op.f("ix_preview_jobs_product_id"), "preview_jobs", ["product_id"])
    op.create_index(
        op.f("ix_preview_jobs_candidate_revision_id"),
        "preview_jobs",
        ["candidate_revision_id"],
    )
    op.create_index(
        "ix_preview_jobs_mapping_digest_attempt",
        "preview_jobs",
        ["mapping_id", "input_digest", "attempt"],
    )


def downgrade() -> None:
    """Remove durable preview attempts."""
    op.drop_index("ix_preview_jobs_mapping_digest_attempt", table_name="preview_jobs")
    op.drop_index(op.f("ix_preview_jobs_candidate_revision_id"), table_name="preview_jobs")
    op.drop_index(op.f("ix_preview_jobs_product_id"), table_name="preview_jobs")
    op.drop_table("preview_jobs")
