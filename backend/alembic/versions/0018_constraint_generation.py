"""Keep optimistic constraint generations across deletion and recreation.

Revision ID: 0018_constraint_generation
Revises: 0017_translation_search_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_constraint_generation"
down_revision: str | None = "0017_translation_search_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Reserve an epoch above every prior SQL INTEGER version for existing keys."""
    op.add_column(
        "translation_keys",
        sa.Column("constraint_generation", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE translation_keys AS key SET constraint_generation = greatest(2147483647, "
        "coalesce((SELECT max(version) FROM translation_constraints "
        "WHERE translation_key_id = key.id), 0))"
    )
    op.create_check_constraint(
        op.f("ck_translation_keys_constraint_generation_non_negative"),
        "translation_keys",
        "constraint_generation BETWEEN 0 AND 9007199254740991",
    )
    op.alter_column(
        "translation_constraints", "version", type_=sa.BigInteger(), existing_type=sa.Integer()
    )
    op.drop_constraint(
        op.f("ck_translation_constraints_version_positive"),
        "translation_constraints",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_translation_constraints_version_positive"),
        "translation_constraints",
        "version BETWEEN 1 AND 9007199254740991",
    )


def downgrade() -> None:
    """Refuse unrepresentable old-schema versions rather than reset live authority."""
    op.alter_column(
        "translation_constraints", "version", type_=sa.Integer(), existing_type=sa.BigInteger()
    )
    op.drop_constraint(
        op.f("ck_translation_constraints_version_positive"),
        "translation_constraints",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_translation_constraints_version_positive"),
        "translation_constraints",
        "version > 0",
    )
    op.drop_constraint(
        op.f("ck_translation_keys_constraint_generation_non_negative"),
        "translation_keys",
        type_="check",
    )
    op.drop_column("translation_keys", "constraint_generation")
