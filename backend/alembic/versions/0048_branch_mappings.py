"""Allow independently configured approval branches for a product's mappings."""

import sqlalchemy as sa

from alembic import op

revision = "0048_branch_mappings"
down_revision = "0047_branch_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_branch_workflows_product_id", "branch_workflows", type_="unique")
    op.create_unique_constraint(
        "uq_branch_workflows_mapping_id", "branch_workflows", ["mapping_id"]
    )
    op.add_column(
        "branch_files",
        sa.Column(
            "path_digest", sa.String(32), sa.Computed("md5(path)", persisted=True), nullable=False
        ),
    )
    op.drop_constraint("pk_branch_files", "branch_files", type_="primary")
    op.create_primary_key("pk_branch_files", "branch_files", ["workflow_id", "path_digest"])


def downgrade() -> None:
    # Refuse downgrade if a product now has more than one workflow; never discard history.
    op.create_unique_constraint(
        "uq_branch_workflows_product_id", "branch_workflows", ["product_id"]
    )
    op.drop_constraint("uq_branch_workflows_mapping_id", "branch_workflows", type_="unique")
    op.drop_constraint("pk_branch_files", "branch_files", type_="primary")
    op.create_primary_key("pk_branch_files", "branch_files", ["workflow_id", "path"])
    op.drop_column("branch_files", "path_digest")
