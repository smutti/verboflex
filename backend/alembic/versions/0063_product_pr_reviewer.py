"""Store the Bitbucket pull request reviewer on the stable product."""

import sqlalchemy as sa

from alembic import op

revision = "0063_product_pr_reviewer"
down_revision = "0062_branch_rate_limit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("pr_reviewer_uuid", sa.Uuid()))
    op.add_column("products", sa.Column("pr_reviewer_name", sa.String(120)))
    op.create_check_constraint(
        "pr_reviewer_complete",
        "products",
        "(pr_reviewer_uuid IS NULL) = (pr_reviewer_name IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("pr_reviewer_complete", "products", type_="check")
    op.drop_column("products", "pr_reviewer_name")
    op.drop_column("products", "pr_reviewer_uuid")
