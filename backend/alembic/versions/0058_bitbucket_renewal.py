"""Separate equivalent token renewal from confirmed connection authority."""

import sqlalchemy as sa

from alembic import op

revision = "0058_bitbucket_renewal"
down_revision = "0057_qt_screenshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legacy credentials have no proven renewal lineage; they remain exact-generation only.
    op.add_column("bitbucket_connections", sa.Column("renewal_start_generation", sa.Integer()))
    op.add_column("bitbucket_connections", sa.Column("client_credentials_digest", sa.String(64)))
    # The source-locale policy now applies independently of the project base.
    # Retire cursors/forms captured under the previous effective-text semantics.
    op.execute("UPDATE source_fallback_policies SET version = version + 1 WHERE enabled")


def downgrade() -> None:
    op.execute("UPDATE source_fallback_policies SET version = version + 1 WHERE enabled")
    op.drop_column("bitbucket_connections", "client_credentials_digest")
    op.drop_column("bitbucket_connections", "renewal_start_generation")
