"""Optional text-location receipts bound to each immutable screenshot."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0052_screenshot_location"
down_revision = "0051_user_deletion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("screenshot_jobs", sa.Column("location", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("screenshot_jobs", "location")
