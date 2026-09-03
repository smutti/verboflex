"""Create stable products and immutable configuration revisions.

Revision ID: 0002_product_revisions
Revises: 0001_auth_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_product_revisions"
down_revision: str | None = "0001_auth_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create UUID products, candidate graphs, and published-row guards."""
    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("name_key", sa.String(length=360), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("active_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(display_name) BETWEEN 1 AND 120",
            name=op.f("ck_products_display_name_length"),
        ),
        sa.CheckConstraint(
            "char_length(name_key) BETWEEN 1 AND 360",
            name=op.f("ck_products_name_key_length"),
        ),
        sa.CheckConstraint(
            "active_revision_id IS NULL OR candidate_revision_id IS NULL "
            "OR active_revision_id <> candidate_revision_id",
            name=op.f("ck_products_distinct_revision_pointers"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("name_key", name="uq_products_name_key"),
    )
    op.create_table(
        "product_revisions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_product_revisions_positive_version")),
        sa.CheckConstraint(
            "(is_published AND published_at IS NOT NULL) "
            "OR (NOT is_published AND published_at IS NULL)",
            name=op.f("ck_product_revisions_publication_timestamp_state"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_product_revisions_product_id_products",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_product_revisions"),
    )
    op.create_index(
        "ix_product_revisions_product_id",
        "product_revisions",
        ["product_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_products_active_revision_id_product_revisions",
        "products",
        "product_revisions",
        ["active_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_products_candidate_revision_id_product_revisions",
        "products",
        "product_revisions",
        ["candidate_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        CREATE FUNCTION prevent_published_product_revision_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.is_published THEN
                RAISE EXCEPTION 'published product revision is immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_product_revisions_immutable_published
        BEFORE UPDATE OR DELETE ON product_revisions
        FOR EACH ROW
        EXECUTE FUNCTION prevent_published_product_revision_mutation()
        """
    )


def downgrade() -> None:
    """Remove product-revision objects in reverse dependency order."""
    op.execute("DROP TRIGGER trg_product_revisions_immutable_published ON product_revisions")
    op.execute("DROP FUNCTION prevent_published_product_revision_mutation()")
    op.drop_constraint(
        "fk_products_candidate_revision_id_product_revisions",
        "products",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_products_active_revision_id_product_revisions",
        "products",
        type_="foreignkey",
    )
    op.drop_index("ix_product_revisions_product_id", table_name="product_revisions")
    op.drop_table("product_revisions")
    op.drop_table("products")
