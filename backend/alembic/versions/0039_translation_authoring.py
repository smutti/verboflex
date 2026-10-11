"""Versioned structural authoring drafts, separate from imported content."""

import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0039_translation_authoring"
down_revision = "0038_audit_events"
branch_labels = None
depends_on = None


FK_CATALOG_SQL = """SELECT coalesce(jsonb_agg(jsonb_build_array(
    conrelid::regclass::text, conname, pg_get_constraintdef(oid))
    ORDER BY conrelid::regclass::text, conname), '[]'::jsonb)::text
    FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace
    AND conrelid::regclass::text NOT LIKE 'maintenance_%'"""
ADDED_FKS = [
    ["translation_authoring_requests", name, definition]
    for name, definition in [
        (
            "fk_authoring_scope",
            "FOREIGN KEY (scope_id) REFERENCES localization_scopes(id) ON DELETE CASCADE",
        ),
        (
            "fk_authoring_parent",
            "FOREIGN KEY (parent_key_id) REFERENCES translation_keys(id) ON DELETE CASCADE",
        ),
        (
            "fk_authoring_creator",
            "FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT",
        ),
        ("fk_authoring_editor", "FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT"),
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


def upgrade() -> None:
    op.create_table(
        "translation_authoring_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scope_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("localization_scopes.id", ondelete="CASCADE", name="fk_authoring_scope"),
            nullable=False,
        ),
        sa.Column(
            "parent_key_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("translation_keys.id", ondelete="CASCADE", name="fk_authoring_parent"),
        ),
        sa.Column("raw_key", sa.Text(), nullable=False),
        sa.Column("language", sa.String(64), nullable=False),
        sa.Column("identity_digest", sa.String(64), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_authoring_creator"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_authoring_editor"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("state IN ('draft','approved','rejected')", name="state"),
        sa.CheckConstraint("version BETWEEN 1 AND 9007199254740991", name="version"),
        sa.CheckConstraint("char_length(raw_key) BETWEEN 1 AND 4096", name="key_bound"),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 1048576",
            name="payload_bound",
        ),
    )
    op.create_index(
        "uq_authoring_identity",
        "translation_authoring_requests",
        ["scope_id", "identity_digest"],
        unique=True,
    )
    op.create_index("ix_authoring_scope_page", "translation_authoring_requests", ["scope_id", "id"])

    for column in ("parent_key_id", "created_by", "updated_by"):
        op.create_index(f"ix_authoring_{column}", "translation_authoring_requests", [column])
    _catalog(True)


def downgrade() -> None:
    op.drop_table("translation_authoring_requests")
    _catalog(False)
