"""Permit canonical HTML values without weakening existing format checks."""

import sqlalchemy as sa

from alembic import op

revision = "0053_html_format"
down_revision = "0052_screenshot_location"
branch_labels = None
depends_on = None

_OLD_FORMATS = "format IN ('android_xml', 'qt_ts', 'json', 'ios_strings', 'xliff')"
_NEW_FORMATS = "format IN ('android_xml', 'qt_ts', 'json', 'ios_strings', 'xliff', 'html')"
_CONSTRAINTS = (
    ("staged_translation_values", "ck_staged_translation_values_format_value"),
    ("translation_value_locators", "ck_translation_value_locators_format_value"),
)


def _replace_constraints(expression: str) -> None:
    for table, constraint in _CONSTRAINTS:
        op.drop_constraint(op.f(constraint), table, type_="check")
        op.create_check_constraint(op.f(constraint), table, expression)


_OLD_AUDIT_ACTIONS = (
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


def _audit_actions(include_html: bool) -> None:
    actions = _OLD_AUDIT_ACTIONS + (
        ("html.language_requested", "html.language_discarded") if include_html else ()
    )
    op.drop_constraint(op.f("ck_audit_entries_known_action"), "audit_entries", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_entries_known_action"),
        "audit_entries",
        "action IN (" + ", ".join(repr(action) for action in actions) + ")",
    )


def upgrade() -> None:
    _replace_constraints(_NEW_FORMATS)
    _audit_actions(True)
    op.drop_constraint(op.f("ck_branch_jobs_kind"), "branch_jobs", type_="check")
    op.create_check_constraint(
        op.f("ck_branch_jobs_kind"),
        "branch_jobs",
        "kind IN ('commit','pull_request','html_language')",
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table, _constraint in _CONSTRAINTS:
        exists = connection.execute(
            sa.text(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE format = 'html')")
        ).scalar_one()
        if exists:
            raise RuntimeError("cannot downgrade while HTML rows exist")
    if connection.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM branch_jobs WHERE kind = 'html_language')")
    ).scalar_one():
        raise RuntimeError("cannot downgrade while HTML language jobs exist")
    if connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM audit_entries WHERE action IN ('html.language_requested', 'html.language_discarded'))"
        )
    ).scalar_one():
        raise RuntimeError("cannot downgrade while HTML language audit entries exist")
    _audit_actions(False)
    _replace_constraints(_OLD_FORMATS)
    op.drop_constraint(op.f("ck_branch_jobs_kind"), "branch_jobs", type_="check")
    op.create_check_constraint(
        op.f("ck_branch_jobs_kind"), "branch_jobs", "kind IN ('commit','pull_request')"
    )
