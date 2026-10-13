"""Bounded expiring screenshot job receipts and authenticated images."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0046_screenshots"
down_revision = "0045_code_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These UUIDs are snapshot identities, as in product_team_events. Expiry erases
    # payloads even after their original product/user has been removed. Every read
    # and worker publication resolves current product, membership and active scope.
    op.create_table(
        "screenshot_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *(
            sa.Column(name, sa.Uuid(), nullable=False)
            for name in ("actor_id", "product_id", "group_id", "scope_id", "execution_id")
        ),
        sa.Column("membership_stamp", sa.String(128), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("request", postgresql.JSONB(), nullable=False),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("image", sa.LargeBinary()),
        sa.Column("image_digest", sa.String(64)),
        sa.Column("error_code", sa.String(64)),
        *(
            sa.Column(name, sa.DateTime(timezone=True), nullable=False)
            for name in ("created_at", "updated_at", "expires_at")
        ),
        sa.CheckConstraint(
            "state IN ('queued','rendering','succeeded','failed','cancelled','expired')",
            name="state",
        ),
        sa.CheckConstraint("image IS NULL OR octet_length(image) <= 8388608", name="image_bound"),
        sa.CheckConstraint("octet_length(inputs::text) <= 8388608", name="input_bound"),
    )
    for name, columns in (
        ("actor_created", ["actor_id", "created_at"]),
        ("group_created", ["group_id", "created_at"]),
        ("state_updated", ["state", "updated_at"]),
    ):
        op.create_index("ix_screenshot_" + name, "screenshot_jobs", columns)


def downgrade() -> None:
    op.drop_table("screenshot_jobs")
