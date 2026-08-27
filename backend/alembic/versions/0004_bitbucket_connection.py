"""Create the singleton encrypted Bitbucket OAuth connection.

Revision ID: 0004_bitbucket_connection
Revises: 0003_repositories
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_bitbucket_connection"
down_revision: str | None = "0003_repositories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create and seed the sole generation authority without credentials."""
    op.create_table(
        "bitbucket_connections",
        sa.Column(
            "id",
            sa.SmallInteger(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "generation",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("access_token_ciphertext", sa.Text(), nullable=True),
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=True),
        sa.Column("scope_profile", sa.String(length=64), nullable=True),
        sa.Column("provider_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
            "id = 1",
            name=op.f("ck_bitbucket_connections_singleton_id"),
        ),
        sa.CheckConstraint(
            "generation >= 0",
            name=op.f("ck_bitbucket_connections_generation_non_negative"),
        ),
        sa.CheckConstraint(
            "(access_token_ciphertext IS NULL) = "
            "(refresh_token_ciphertext IS NULL)",
            name=op.f("ck_bitbucket_connections_credential_pair_state"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bitbucket_connections")),
    )
    op.execute(sa.text("INSERT INTO bitbucket_connections DEFAULT VALUES"))


def downgrade() -> None:
    """Remove the organizational connection authority."""
    op.drop_table("bitbucket_connections")
