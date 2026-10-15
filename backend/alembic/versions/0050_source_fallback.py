"""Versioned per-product confirmed source-language fallback."""

import json

import sqlalchemy as sa

from alembic import op

revision = "0050_source_fallback"
down_revision = "0049_approval_target"
branch_labels = None
depends_on = None


FK_CATALOG_SQL = """SELECT coalesce(jsonb_agg(jsonb_build_array(
    conrelid::regclass::text, conname, pg_get_constraintdef(oid))
    ORDER BY conrelid::regclass::text, conname), '[]'::jsonb)::text
    FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace
    AND conrelid::regclass::text NOT LIKE 'maintenance_%'"""
ADDED_FKS = [
    [
        "source_fallback_policies",
        "fk_source_fallback_policies_product_id_products",
        "FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE",
    ],
    [
        "source_fallback_texts",
        "fk_source_fallback_texts_product_id_source_fallback_policies",
        "FOREIGN KEY (product_id) REFERENCES source_fallback_policies(product_id) "
        "ON DELETE CASCADE",
    ],
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


def _maintenance_sources(upgrade: bool) -> None:
    """Extend the frozen deletion allowlist and exact-row ownership resolver."""
    changes = (
        (
            "verboflex_maintenance_authorize",
            "NEW.table_name NOT IN (",
            "NEW.table_name NOT IN ('source_fallback_texts','source_fallback_policies',",
        ),
        (
            "verboflex_maintenance_row_owner",
            "BEGIN CASE tab ",
            "BEGIN CASE tab "
            "WHEN 'source_fallback_policies' THEN SELECT t.product_id INTO result "
            "FROM source_fallback_policies t WHERE t.product_id=(row_key->>'product_id')::uuid; "
            "WHEN 'source_fallback_texts' THEN SELECT t.product_id INTO result "
            "FROM source_fallback_texts t WHERE t.product_id=(row_key->>'product_id')::uuid "
            "AND t.source_digest=row_key->>'source_digest'; ",
        ),
    )
    connection = op.get_bind()
    for name, before, after in changes:
        installed, current = connection.execute(
            sa.text(
                "SELECT installed_definition, pg_get_functiondef(to_regproc(:name)) "
                "FROM maintenance_schema WHERE name=:name"
            ),
            {"name": name},
        ).one()
        old, new = (before, after) if upgrade else (after, before)
        if current != installed or current.count(old) != 1:
            raise ValueError("unexpected maintenance source fallback guard definition")
        op.execute(current.replace(old, new, 1))
        connection.execute(
            sa.text(
                "UPDATE maintenance_schema SET installed_definition="
                "pg_get_functiondef(to_regproc(:name)) WHERE name=:name"
            ),
            {"name": name},
        )


def upgrade() -> None:
    op.create_table(
        "source_fallback_policies",
        sa.Column(
            "product_id",
            sa.UUID(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(64)),
        sa.CheckConstraint(
            "version >= 1", name=op.f("ck_source_fallback_policies_version_positive")
        ),
    )
    op.create_table(
        "source_fallback_texts",
        sa.Column(
            "product_id",
            sa.UUID(),
            sa.ForeignKey("source_fallback_policies.product_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("source_digest", sa.String(64), primary_key=True),
        sa.Column("source_text", sa.Text(), nullable=False),
    )

    _catalog(True)
    _maintenance_sources(True)


def downgrade() -> None:
    _maintenance_sources(False)
    op.drop_table("source_fallback_texts")
    op.drop_table("source_fallback_policies")
    _catalog(False)
