"""Project glossary and content-free authoring audit receipts."""

import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0041_glossary_authoring_audit"
down_revision = "0040_current_translation_reuse"
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
)
NEW_ACTIONS = (
    "authoring.saved",
    "authoring.approved",
    "authoring.rejected",
    "authoring.reopened",
    "authoring.deleted",
    "glossary.saved",
    "glossary.deleted",
)

FK_CATALOG_SQL = """SELECT coalesce(jsonb_agg(jsonb_build_array(
    conrelid::regclass::text, conname, pg_get_constraintdef(oid))
    ORDER BY conrelid::regclass::text, conname), '[]'::jsonb)::text
    FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace
    AND conrelid::regclass::text NOT LIKE 'maintenance_%'"""
ADDED_FKS = [
    ["glossary_entries", name, definition]
    for name, definition in [
        (
            "fk_glossary_product",
            "FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE",
        ),
        ("fk_glossary_creator", "FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT"),
        ("fk_glossary_editor", "FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT"),
    ]
]


def _catalog(upgrade: bool) -> None:
    connection = op.get_bind()
    installed = connection.scalar(
        sa.text("SELECT installed_definition FROM maintenance_schema WHERE name='foreign_keys'")
    )
    current = connection.scalar(sa.text(FK_CATALOG_SQL))
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
        "glossary_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE", name="fk_glossary_product"),
            nullable=False,
        ),
        sa.Column("identity_digest", sa.String(64), nullable=False),
        sa.Column("source_language", sa.String(32), nullable=False),
        sa.Column("target_language", sa.String(32), nullable=False),
        sa.Column("source_term", sa.String(256), nullable=False),
        sa.Column("target_term", sa.String(256), nullable=False),
        sa.Column("forbidden", sa.Boolean(), nullable=False),
        sa.Column("case_sensitive", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(1000), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_glossary_creator"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_glossary_editor"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version BETWEEN 1 AND 9007199254740991", name="version"),
        sa.CheckConstraint("char_length(source_term) BETWEEN 1 AND 256", name="source_bound"),
        sa.CheckConstraint("char_length(target_term) BETWEEN 1 AND 256", name="target_bound"),
    )
    op.create_index(
        "uq_glossary_identity", "glossary_entries", ["product_id", "identity_digest"], unique=True
    )
    op.create_index(
        "ix_glossary_pair",
        "glossary_entries",
        ["product_id", "source_language", "target_language", "id"],
    )
    op.create_index("ix_glossary_creator", "glossary_entries", ["created_by"])
    op.create_index("ix_glossary_editor", "glossary_entries", ["updated_by"])
    _catalog(True)
    _audit(OLD_ACTIONS + NEW_ACTIONS)


def downgrade() -> None:
    # Preserve audit receipts: downgrade deliberately refuses while new actions exist.
    _audit(OLD_ACTIONS)
    op.drop_table("glossary_entries")
    _catalog(False)
