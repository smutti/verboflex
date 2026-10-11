"""Create revision-owned product repository mappings.

Revision ID: 0005_product_mappings
Revises: 0004_bitbucket_connection
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_product_mappings"
down_revision: str | None = "0004_bitbucket_connection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create mapping identity, explicit repository sides, and target sets."""
    op.create_table(
        "product_repository_mappings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topology", sa.String(length=16), nullable=False),
        sa.Column("identity_key", sa.String(length=1200), nullable=False),
        sa.Column(
            "selected_layout_candidate_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("selected_layout_version", sa.Integer(), nullable=True),
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
            "topology IN ('direct', 'separate')",
            name=op.f("ck_product_repository_mappings_topology_value"),
        ),
        sa.CheckConstraint(
            "char_length(identity_key) BETWEEN 1 AND 1200",
            name=op.f("ck_product_repository_mappings_identity_key_length"),
        ),
        sa.CheckConstraint(
            "(selected_layout_candidate_id IS NULL AND selected_layout_version IS NULL) OR "
            "(selected_layout_candidate_id IS NOT NULL AND selected_layout_version > 0)",
            name=op.f("ck_product_repository_mappings_selected_layout_state"),
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["product_revisions.id"],
            name=op.f("fk_product_repository_mappings_revision_id_product_revisions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_repository_mappings")),
        sa.UniqueConstraint(
            "revision_id",
            "identity_key",
            name="uq_product_repository_mappings_revision_identity",
        ),
    )
    op.create_index(
        op.f("ix_product_repository_mappings_revision_id"),
        "product_repository_mappings",
        ["revision_id"],
        unique=False,
    )
    op.create_table(
        "product_mapping_repository_sides",
        sa.Column("mapping_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_branch", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "role IN ('direct', 'keys', 'translations')",
            name=op.f("ck_product_mapping_repository_sides_role_value"),
        ),
        sa.CheckConstraint(
            "char_length(source_branch) BETWEEN 1 AND 255",
            name=op.f("ck_product_mapping_repository_sides_source_branch_length"),
        ),
        sa.ForeignKeyConstraint(
            ["mapping_id"],
            ["product_repository_mappings.id"],
            name=op.f("fk_product_mapping_repository_sides_mapping_id_product_repository_mappings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_product_mapping_repository_sides_repository_id_repositories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "mapping_id",
            "role",
            name=op.f("pk_product_mapping_repository_sides"),
        ),
    )
    op.create_table(
        "product_mapping_allowed_targets",
        sa.Column("mapping_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(branch) BETWEEN 1 AND 255",
            name=op.f("ck_product_mapping_allowed_targets_branch_length"),
        ),
        sa.ForeignKeyConstraint(
            ["mapping_id"],
            ["product_repository_mappings.id"],
            name=op.f("fk_product_mapping_allowed_targets_mapping_id_product_repository_mappings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "mapping_id",
            "branch",
            name=op.f("pk_product_mapping_allowed_targets"),
        ),
    )
    op.create_index(
        "uq_product_mapping_allowed_targets_one_default",
        "product_mapping_allowed_targets",
        ["mapping_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    """Remove mapping leaves before their revision-owned root."""
    op.drop_index(
        "uq_product_mapping_allowed_targets_one_default",
        table_name="product_mapping_allowed_targets",
    )
    op.drop_table("product_mapping_allowed_targets")
    op.drop_table("product_mapping_repository_sides")
    op.drop_index(
        op.f("ix_product_repository_mappings_revision_id"),
        table_name="product_repository_mappings",
    )
    op.drop_table("product_repository_mappings")
