"""Add history-preserving logical product deletion and live-name uniqueness."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0024_product_logical_deletion"
down_revision = "0023_duplicate_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "products",
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_products_deleted_by_users",
        "products",
        "users",
        ["deleted_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_products_deleted_identity_complete",
        "products",
        "(deleted_at IS NULL) = (deleted_by IS NULL)",
    )
    op.create_check_constraint(
        "ck_products_deleted_inactive",
        "products",
        "deleted_at IS NULL OR NOT is_active",
    )
    op.drop_constraint("uq_products_name_key", "products", type_="unique")
    op.create_index(
        "uq_products_live_name_key",
        "products",
        ["name_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    duplicate = connection.execute(
        sa.text("SELECT name_key FROM products GROUP BY name_key HAVING count(*) > 1 LIMIT 1")
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "cannot downgrade logical product deletion after a deleted name has been reused"
        )
    op.drop_index("uq_products_live_name_key", table_name="products")
    op.create_unique_constraint("uq_products_name_key", "products", ["name_key"])
    op.drop_constraint("ck_products_deleted_inactive", "products", type_="check")
    op.drop_constraint("ck_products_deleted_identity_complete", "products", type_="check")
    op.drop_constraint("fk_products_deleted_by_users", "products", type_="foreignkey")
    op.drop_column("products", "deleted_by")
    op.drop_column("products", "deleted_at")
