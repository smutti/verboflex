"""OAuth clients, grants and hashed credentials for HTTP MCP."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0036_mcp_oauth"
down_revision = "0035_retired_translation_purge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_oauth_clients",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("redirect_uris", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("auth_method", sa.String(length=32), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_oauth_clients")),
    )
    op.create_table(
        "mcp_oauth_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("resource", sa.String(length=2048), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["mcp_oauth_clients.id"],
            name=op.f("fk_mcp_oauth_grants_client_id_mcp_oauth_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_mcp_oauth_grants_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_oauth_grants")),
    )
    op.create_index(
        op.f("ix_mcp_oauth_grants_client_id"), "mcp_oauth_grants", ["client_id"], unique=False
    )
    op.create_index(
        op.f("ix_mcp_oauth_grants_expires_at"), "mcp_oauth_grants", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_mcp_oauth_grants_user_id"), "mcp_oauth_grants", ["user_id"], unique=False
    )
    op.create_table(
        "mcp_oauth_requests",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=80), nullable=False),
        sa.Column("redirect_uri", sa.String(length=2048), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("resource", sa.String(length=2048), nullable=False),
        sa.Column("state", sa.String(length=2048), nullable=True),
        sa.Column("code_challenge", sa.String(length=43), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=True),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
        sa.Column("grant_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["mcp_oauth_clients.id"],
            name=op.f("fk_mcp_oauth_requests_client_id_mcp_oauth_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"],
            ["mcp_oauth_grants.id"],
            name=op.f("fk_mcp_oauth_requests_grant_id_mcp_oauth_grants"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_mcp_oauth_requests_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_oauth_requests")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_mcp_oauth_requests_code_hash")),
    )
    op.create_index(
        op.f("ix_mcp_oauth_requests_client_id"), "mcp_oauth_requests", ["client_id"], unique=False
    )
    op.create_index(
        op.f("ix_mcp_oauth_requests_expires_at"), "mcp_oauth_requests", ["expires_at"], unique=False
    )
    op.create_table(
        "mcp_oauth_tokens",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["grant_id"],
            ["mcp_oauth_grants.id"],
            name=op.f("fk_mcp_oauth_tokens_grant_id_mcp_oauth_grants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_mcp_oauth_tokens")),
    )
    op.create_index(
        op.f("ix_mcp_oauth_tokens_expires_at"), "mcp_oauth_tokens", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_mcp_oauth_tokens_grant_id"), "mcp_oauth_tokens", ["grant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("mcp_oauth_tokens")
    op.drop_table("mcp_oauth_requests")
    op.drop_table("mcp_oauth_grants")
    op.drop_table("mcp_oauth_clients")
