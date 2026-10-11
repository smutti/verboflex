"""Exact reuse lookup without storing another copy of translation content."""

from alembic import op

revision = "0040_current_translation_reuse"
down_revision = "0039_translation_authoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE INDEX ix_translation_values_reuse_source_exact
        ON translation_values (sha256(replace(source_text,chr(92),chr(92)||chr(92))::bytea), language, scope_id)
        WHERE NOT is_deleted AND source_text IS NOT NULL
            AND char_length(source_text) BETWEEN 1 AND 4096""")


def downgrade() -> None:
    op.drop_index("ix_translation_values_reuse_source_exact", table_name="translation_values")
