"""Permit access-only Bitbucket client-credentials generations.

Revision ID: 0008_bitbucket_client_credentials
Revises: 0007_preview_confirmations
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_bitbucket_client_credentials"
down_revision: str | None = "0007_preview_confirmations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CLIENT_CREDENTIAL_STATE = (
    "(access_token_ciphertext IS NULL AND refresh_token_ciphertext IS NULL) OR "
    "(access_token_ciphertext IS NOT NULL AND refresh_token_ciphertext IS NULL) OR "
    "(access_token_ciphertext IS NOT NULL AND refresh_token_ciphertext IS NOT NULL)"
)
LEGACY_CREDENTIAL_PAIR_STATE = (
    "(access_token_ciphertext IS NULL) = (refresh_token_ciphertext IS NULL)"
)


def upgrade() -> None:
    """Allow disconnected, legacy paired, and access-only credential states."""
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.drop_constraint(
        op.f("ck_bitbucket_connections_credential_pair_state"),
        "bitbucket_connections",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_bitbucket_connections_credential_state"),
        "bitbucket_connections",
        CLIENT_CREDENTIAL_STATE,
    )


def downgrade() -> None:
    """Invalidate access-only authority before restoring the legacy pair rule."""
    op.execute(
        sa.text(
            "UPDATE bitbucket_connections SET "
            "generation = generation + 1, "
            "access_token_ciphertext = NULL, "
            "scope_profile = NULL, "
            "provider_expires_at = NULL, "
            "connected_at = NULL, "
            "revoked_at = CURRENT_TIMESTAMP, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE access_token_ciphertext IS NOT NULL "
            "AND refresh_token_ciphertext IS NULL"
        )
    )
    op.drop_constraint(
        op.f("ck_bitbucket_connections_credential_state"),
        "bitbucket_connections",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_bitbucket_connections_credential_pair_state"),
        "bitbucket_connections",
        LEGACY_CREDENTIAL_PAIR_STATE,
    )
