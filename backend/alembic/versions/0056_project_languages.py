"""Extend the durable branch queue to all catalog formats."""

import sqlalchemy as sa

from alembic import op

revision = "0056_project_languages"
down_revision = "0055_web_localization"
branch_labels = None
depends_on = None

_ACTIONS = (
    "language.requested",
    "language.discarded",
    "html.language_requested",
    "html.language_discarded",
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
    "user.deleted",
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


def _constraints(enabled: bool) -> None:
    kinds = "'commit','pull_request','html_language'" + (",'language'" if enabled else "")
    op.drop_constraint(op.f("ck_branch_jobs_kind"), "branch_jobs", type_="check")
    op.create_check_constraint(op.f("ck_branch_jobs_kind"), "branch_jobs", f"kind IN ({kinds})")
    actions = _ACTIONS if enabled else tuple(a for a in _ACTIONS if not a.startswith("language."))
    op.drop_constraint(op.f("ck_audit_entries_known_action"), "audit_entries", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_entries_known_action"),
        "audit_entries",
        "action IN (" + ", ".join(repr(a) for a in actions) + ")",
    )


def upgrade() -> None:
    _constraints(True)


def downgrade() -> None:
    connection = op.get_bind()
    for query in (
        "SELECT EXISTS (SELECT 1 FROM branch_jobs WHERE kind = 'language')",
        "SELECT EXISTS (SELECT 1 FROM audit_entries "
        "WHERE action IN ('language.requested','language.discarded'))",
    ):
        if connection.execute(sa.text(query)).scalar_one():
            raise RuntimeError("cannot downgrade while project language history exists")
    _constraints(False)
