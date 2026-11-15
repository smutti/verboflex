"""Freeze Qt screenshot scenarios alongside their imported catalogs."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0057_qt_screenshots"
down_revision = "0056_project_languages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("import_executions", sa.Column("qt_context", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(
            sa.text("SELECT EXISTS (SELECT 1 FROM import_executions WHERE qt_context IS NOT NULL)")
        )
        .scalar_one()
    ):
        raise RuntimeError("Cannot discard imported Qt screenshot contexts")
    op.drop_column("import_executions", "qt_context")
