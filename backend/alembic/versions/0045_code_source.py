"""Revision-owned code extraction and immutable import catalogs."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0045_code_source"
down_revision = "0044_product_membership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_repository_mappings", sa.Column("code_source", postgresql.JSONB()))
    op.create_check_constraint(
        "code_source_separate",
        "product_repository_mappings",
        "code_source IS NULL OR (topology = 'separate' AND jsonb_typeof(code_source) = 'object')",
    )
    op.add_column("import_executions", sa.Column("code_catalog", postgresql.JSONB()))


def downgrade() -> None:
    op.drop_column("import_executions", "code_catalog")
    op.drop_constraint("code_source_separate", "product_repository_mappings", type_="check")
    op.drop_column("product_repository_mappings", "code_source")
