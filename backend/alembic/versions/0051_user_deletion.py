"""Irreversible account removal with an anonymous historical identity."""

import sqlalchemy as sa

from alembic import op

revision = "0051_user_deletion"
down_revision = "0050_source_fallback"
branch_labels = None
depends_on = None

OLD_ACTIONS = (
    "branch.configured",
    "branch.approval_queued",
    "branch.pr_requested",
    "branch.retry_requested",
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
    "authoring.saved",
    "authoring.approved",
    "authoring.rejected",
    "authoring.reopened",
    "authoring.deleted",
    "glossary.saved",
    "glossary.deleted",
)


def _audit_actions(actions: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_audit_entries_known_action"), "audit_entries", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_entries_known_action"),
        "audit_entries",
        "action IN (" + ", ".join(repr(action) for action in actions) + ")",
    )


def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f("ck_users_deleted_account_disabled"),
        "users",
        "deleted_at IS NULL OR (NOT is_active AND NOT must_change_password)",
    )
    _audit_actions((*OLD_ACTIONS, "user.deleted"))


def downgrade() -> None:
    # Never make removed identities reactivatable or discard deletion receipts.
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM users WHERE deleted_at IS NOT NULL) OR "
            "EXISTS (SELECT 1 FROM audit_entries WHERE action='user.deleted')"
        )
    ):
        raise RuntimeError("User deletions cannot be undone by a schema downgrade")
    _audit_actions(OLD_ACTIONS)
    op.drop_constraint(op.f("ck_users_deleted_account_disabled"), "users", type_="check")
    op.drop_column("users", "deleted_at")
