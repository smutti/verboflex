"""Persist exact normalized base-language authority on each mapping.

Revision ID: 0015_mapping_base_language
Revises: 0014_import_source_reference_insert_guard
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_mapping_base_language"
down_revision: str | None = "0014_import_source_reference_insert_guard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable legacy-safe base-language authority with exact checks."""
    op.add_column(
        "product_repository_mappings",
        sa.Column("base_language", sa.String(), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_product_repository_mappings_base_language_length"),
        "product_repository_mappings",
        "base_language IS NULL OR char_length(base_language) BETWEEN 1 AND 64",
    )
    op.create_check_constraint(
        op.f("ck_product_repository_mappings_base_language_normalized"),
        "product_repository_mappings",
        "base_language IS NULL OR base_language ~ "
        "'^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$'",
    )


def downgrade() -> None:
    """Remove only mapping base-language authority and its checks."""
    op.drop_constraint(
        op.f("ck_product_repository_mappings_base_language_normalized"),
        "product_repository_mappings",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_product_repository_mappings_base_language_length"),
        "product_repository_mappings",
        type_="check",
    )
    op.drop_column("product_repository_mappings", "base_language")
