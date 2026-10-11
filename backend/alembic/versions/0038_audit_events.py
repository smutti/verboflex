"""Add bounded transactional mutation receipts without retaining domain content."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0038_audit_events"
down_revision = "0037_mcp_maintenance_catalog"
branch_labels = None
depends_on = None

# Frozen independently of application code for reproducible historical migrations.
ACTIONS = (
    "product.created",
    "product.updated",
    "product.published",
    "product.deactivated",
    "product.reactivated",
    "product.deleted",
    "mapping.created",
    "mapping.updated",
    "repository.registered",
    "workspace.updated",
    "user.created",
    "user.updated",
    "user.password_reset",
    "user.password_changed",
    "user.deactivated",
    "user.reactivated",
    "constraint.updated",
    "constraint.deleted",
    "preview.requested",
    "import.requested",
    "bitbucket.connected",
    "bitbucket.refreshed",
    "bitbucket.revoked",
)


def upgrade() -> None:
    op.create_table(
        "audit_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_kind", sa.String(8), nullable=False),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.CheckConstraint(
            "action IN (" + ", ".join(repr(value) for value in ACTIONS) + ")",
            name=op.f("ck_audit_entries_known_action"),
        ),
        sa.CheckConstraint(
            "(actor_kind = 'user' AND actor_id IS NOT NULL) OR "
            "(actor_kind IN ('operator', 'system') AND actor_id IS NULL)",
            name=op.f("ck_audit_entries_actor_identity"),
        ),
    )
    op.create_index(
        "ix_audit_entries_entity_time", "audit_entries", ["entity_id", "occurred_at", "id"]
    )
    op.create_index(
        "ix_audit_entries_actor_time", "audit_entries", ["actor_id", "occurred_at", "id"]
    )
    # No FK or trigger changes: the exact maintenance catalog remains unchanged.


def downgrade() -> None:
    op.drop_table("audit_entries")
