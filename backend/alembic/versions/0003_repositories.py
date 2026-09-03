"""Create the global reusable repository registry.

Revision ID: 0003_repositories
Revises: 0002_product_revisions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_repositories"
down_revision: str | None = "0002_product_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create normalized provider identities without product or credential state."""
    op.create_table(
        "repositories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("workspace", sa.String(length=100), nullable=False),
        sa.Column("repository_slug", sa.String(length=100), nullable=False),
        sa.Column("descriptive_name", sa.String(length=120), nullable=True),
        sa.Column("descriptive_name_key", sa.String(length=360), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "workspace ~ '^[a-z0-9][a-z0-9_-]{0,99}$'",
            name=op.f("ck_repositories_workspace_normalized"),
        ),
        sa.CheckConstraint(
            "repository_slug ~ '^[a-z0-9][a-z0-9_-]{0,99}$'",
            name=op.f("ck_repositories_repository_slug_normalized"),
        ),
        sa.CheckConstraint(
            "(descriptive_name IS NULL AND descriptive_name_key IS NULL) OR "
            "(char_length(descriptive_name) BETWEEN 1 AND 120 AND "
            "char_length(descriptive_name_key) BETWEEN 1 AND 360)",
            name=op.f("ck_repositories_descriptive_name_state"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repositories")),
        sa.UniqueConstraint(
            "workspace",
            "repository_slug",
            name="uq_repositories_provider_identity",
        ),
    )


def downgrade() -> None:
    """Remove the standalone repository registry."""
    op.drop_table("repositories")
