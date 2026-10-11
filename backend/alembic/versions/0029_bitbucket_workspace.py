"""Configure one Bitbucket workspace for repository selection.

Revision ID: 0029_bitbucket_workspace
Revises: 0028_review_workspace
"""

import sqlalchemy as sa

from alembic import op

revision = "0029_bitbucket_workspace"
down_revision = "0028_review_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bitbucket_connections", sa.Column("workspace", sa.String(100), nullable=True))
    # Preserve the administrator's existing choice only when it is unambiguous.
    op.execute("""
        UPDATE bitbucket_connections
        SET workspace = (SELECT min(workspace) FROM repositories)
        WHERE (SELECT count(DISTINCT workspace) FROM repositories) = 1
    """)


def downgrade() -> None:
    op.drop_column("bitbucket_connections", "workspace")
