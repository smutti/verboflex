"""Store reproducible repository images on their immutable import execution."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0054_html_preview_images"
down_revision = "0053_html_format"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "import_executions",
        sa.Column("html_preview_images", postgresql.JSONB(none_as_null=True), nullable=True),
    )


def downgrade() -> None:
    # These are derived previews, recoverable by refreshing the source.
    op.drop_column("import_executions", "html_preview_images")
