"""Persist version-bound bulk approvals for durable Celery processing."""

import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0059_authoring_bulk_approval"
down_revision = "0058_bitbucket_renewal"
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


ADDED_FKS = [
    [
        "authoring_approvals",
        "fk_authoring_approvals_product_id_products",
        "FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE",
    ],
    [
        "authoring_approvals",
        "fk_authoring_approvals_actor_id_users",
        "FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE RESTRICT",
    ],
]


def _catalog(upgrade: bool) -> None:
    connection = op.get_bind()
    installed = connection.scalar(
        sa.text("SELECT installed_definition FROM maintenance_schema WHERE name='foreign_keys'")
    )
    current = connection.scalar(
        sa.text(
            """SELECT coalesce(jsonb_agg(jsonb_build_array(
                conrelid::regclass::text, conname, pg_get_constraintdef(oid))
                ORDER BY conrelid::regclass::text, conname), '[]'::jsonb)::text
                FROM pg_constraint WHERE contype='f'
                AND connamespace='public'::regnamespace
                AND conrelid::regclass::text NOT LIKE 'maintenance_%'"""
        )
    )
    expected = json.loads(installed)
    expected = (
        expected + ADDED_FKS if upgrade else [row for row in expected if row not in ADDED_FKS]
    )
    if sorted(json.loads(current)) != sorted(expected):
        raise ValueError("unexpected maintenance foreign key changes")
    connection.execute(
        sa.text(
            "UPDATE maintenance_schema SET installed_definition=:catalog WHERE name='foreign_keys'"
        ),
        {"catalog": current},
    )


def _audit(enabled: bool) -> None:
    actions = _ACTIONS + (("authoring.bulk_queued", "authoring.bulk_approved") if enabled else ())
    op.drop_constraint(op.f("ck_audit_entries_known_action"), "audit_entries", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_entries_known_action"),
        "audit_entries",
        "action IN (" + ", ".join(repr(a) for a in actions) + ")",
    )


def upgrade() -> None:
    _audit(True)
    op.create_table(
        "authoring_approvals",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "product_id",
            sa.UUID(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("membership", sa.String(80), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("selection", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("error", sa.String(1024)),
        sa.Column("branch_job_ids", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("state IN ('queued','succeeded','failed')", name="state"),
        sa.CheckConstraint(
            "jsonb_typeof(selection) = 'array' "
            "AND jsonb_array_length(selection) BETWEEN 1 AND 5000 "
            "AND octet_length(selection::text) <= 1048576",
            name="selection_bound",
        ),
    )
    op.create_index(
        "ix_authoring_approvals_product", "authoring_approvals", ["product_id", "created_at"]
    )
    op.create_index(
        "uq_authoring_approvals_pending",
        "authoring_approvals",
        ["product_id"],
        unique=True,
        postgresql_where=sa.text("state = 'queued'"),
    )

    _catalog(True)


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM audit_entries WHERE action IN "
                "('authoring.bulk_queued','authoring.bulk_approved'))"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("cannot downgrade while bulk approval history exists")
    op.drop_table("authoring_approvals")
    _catalog(False)
    _audit(False)
