"""Add explicit JSON localization profiles for direct mappings."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0055_web_localization"
down_revision = "0054_html_preview_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_repository_mappings",
        sa.Column("localization_profile", postgresql.JSONB(), nullable=True),
    )

    op.create_check_constraint(
        "web_profile_direct",
        "product_repository_mappings",
        "localization_profile IS NULL OR (topology = 'direct' "
        "AND jsonb_typeof(localization_profile) = 'object')",
    )
    op.add_column("import_executions", sa.Column("web_context", postgresql.JSONB(), nullable=True))

    op.add_column("screenshot_jobs", sa.Column("receipt", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM product_repository_mappings "
                "WHERE localization_profile IS NOT NULL) "
                "OR EXISTS (SELECT 1 FROM import_executions WHERE web_context IS NOT NULL) "
                "OR EXISTS (SELECT 1 FROM screenshot_jobs WHERE receipt IS NOT NULL)"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Cannot downgrade configured web localization profiles")
    op.drop_constraint("web_profile_direct", "product_repository_mappings", type_="check")
    op.drop_column("screenshot_jobs", "receipt")
    op.drop_column("import_executions", "web_context")
    op.drop_column("product_repository_mappings", "localization_profile")
