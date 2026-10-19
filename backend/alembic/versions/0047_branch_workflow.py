"""Approval commit workflow, separate from PR publication."""

import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0047_branch_workflow"
down_revision = "0046_screenshots"
branch_labels = None
depends_on = None


OLD_ACTIONS = (
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
NEW_ACTIONS = (
    "branch.configured",
    "branch.approval_queued",
    "branch.pr_requested",
    "branch.retry_requested",
)
ADDED_FKS = [
    [
        "branch_workflows",
        "fk_branch_workflows_product_id_products",
        "FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT",
    ],
    [
        "branch_workflows",
        "fk_branch_workflows_mapping_id_product_repository_mappings",
        "FOREIGN KEY (mapping_id) REFERENCES product_repository_mappings(id) ON DELETE RESTRICT",
    ],
    [
        "branch_workflows",
        "fk_branch_workflows_repository_id_repositories",
        "FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE RESTRICT",
    ],
    [
        "branch_workflows",
        "fk_branch_workflows_created_by_users",
        "FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT",
    ],
    [
        "branch_jobs",
        "fk_branch_jobs_workflow_id_branch_workflows",
        "FOREIGN KEY (workflow_id) REFERENCES branch_workflows(id) ON DELETE RESTRICT",
    ],
    [
        "branch_jobs",
        "fk_branch_jobs_actor_id_users",
        "FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE RESTRICT",
    ],
    [
        "branch_files",
        "fk_branch_files_workflow_id_branch_workflows",
        "FOREIGN KEY (workflow_id) REFERENCES branch_workflows(id) ON DELETE RESTRICT",
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


def _audit(actions: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_audit_entries_known_action"), "audit_entries", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_entries_known_action"),
        "audit_entries",
        "action IN (" + ", ".join(repr(a) for a in actions) + ")",
    )


def upgrade() -> None:
    op.create_table(
        "branch_workflows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "mapping_id",
            sa.Uuid(),
            sa.ForeignKey("product_repository_mappings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("work_branch", sa.String(255), nullable=False),
        sa.Column("target_branch", sa.String(255), nullable=False),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("product_id"),
        sa.UniqueConstraint("repository_id", "work_branch"),
        sa.CheckConstraint("work_branch <> target_branch", name="distinct_branches"),
    )
    op.create_table(
        "branch_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sequence", sa.Integer(), sa.Identity(), unique=True, nullable=False),
        sa.Column(
            "workflow_id",
            sa.Uuid(),
            sa.ForeignKey("branch_workflows.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("activity_id", sa.Uuid(), unique=True),
        sa.Column(
            "actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("membership", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("label", sa.String(1024), nullable=False),
        sa.Column("authority", sa.LargeBinary()),
        sa.Column("intent", pg.JSONB()),
        sa.Column("commit_hash", sa.String(40)),
        sa.Column("pr_id", sa.Integer()),
        sa.Column("pr_url", sa.String(4096)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("owner", sa.Uuid()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("kind IN ('commit','pull_request')", name="kind"),
        sa.CheckConstraint(
            "state IN ('queued','running','sending','committed','open',"
            "'merged','declined','blocked')",
            name="state",
        ),
        sa.CheckConstraint(
            "authority IS NULL OR octet_length(authority) <= 134217728", name="authority_bound"
        ),
        sa.CheckConstraint(
            "intent IS NULL OR octet_length(intent::text) <= 134217728", name="intent_bound"
        ),
    )
    op.create_index("ix_branch_jobs_workflow_id", "branch_jobs", ["workflow_id"])
    op.create_table(
        "branch_files",
        sa.Column(
            "workflow_id",
            sa.Uuid(),
            sa.ForeignKey("branch_workflows.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("path", sa.String(4096), primary_key=True),
        sa.Column("baseline_sha256", sa.String(64), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("edits", sa.LargeBinary(), nullable=False),
    )

    _catalog(True)
    _audit(OLD_ACTIONS + NEW_ACTIONS)


def downgrade() -> None:
    _audit(OLD_ACTIONS)
    op.drop_table("branch_files")
    op.drop_table("branch_jobs")
    op.drop_table("branch_workflows")
    _catalog(False)
