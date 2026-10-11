"""Separate current PR heads from immutable submission receipts."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0042_pull_request_tracking"
down_revision = "0041_glossary_authoring_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("change_sets", sa.Column("pr_tracking", postgresql.JSONB(), nullable=True))
    op.drop_constraint(op.f("ck_change_set_events_event_kind"), "change_set_events", type_="check")
    op.create_check_constraint(
        op.f("ck_change_set_events_event_kind"),
        "change_set_events",
        "event_kind IN ('send_intent','observation','reauthorization','finalization','pr_status')",
    )


def downgrade() -> None:
    # Live observations are audit evidence; never silently discard them on downgrade.
    op.drop_constraint(op.f("ck_change_set_events_event_kind"), "change_set_events", type_="check")
    op.create_check_constraint(
        op.f("ck_change_set_events_event_kind"),
        "change_set_events",
        "event_kind IN ('send_intent','observation','reauthorization','finalization')",
    )
    op.drop_column("change_sets", "pr_tracking")
