"""Persist bounded read-only submission review intents.

Revision ID: 0030_submission_reviews
Revises: 0029_bitbucket_workspace
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0030_submission_reviews"
down_revision = "0029_bitbucket_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submission_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_token_version", sa.Integer(), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selection", postgresql.JSONB(), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("prepared_payload", sa.LargeBinary()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id", "revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("state IN ('queued','running','ready','failed')", name="state_value"),
        sa.CheckConstraint("attempt >= 1", name="attempt_positive"),
        sa.CheckConstraint("octet_length(prepared_payload) <= 134217728", name="payload_bound"),
        sa.CheckConstraint(
            "(state = 'ready') = (prepared_payload IS NOT NULL)", name="ready_payload"
        ),
        sa.CheckConstraint(
            "(state IN ('ready','failed')) = (finished_at IS NOT NULL)", name="terminal_time"
        ),
    )
    op.create_index(
        "ix_submission_reviews_actor_product_digest",
        "submission_reviews",
        ["actor_id", "product_id", "input_digest"],
    )


def downgrade() -> None:
    op.drop_table("submission_reviews")
