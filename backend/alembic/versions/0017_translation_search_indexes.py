"""Add translation search indexes after asserting external pg_trgm support.

Revision ID: 0017_translation_search_indexes
Revises: 0016_canonical_translations
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_translation_search_indexes"
down_revision: str | None = "0016_canonical_translations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PG_TRGM_CAPABILITY_ASSERTION = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'
    ) OR NOT EXISTS (
        SELECT 1
        FROM pg_opclass AS operator_class
        JOIN pg_am AS access_method ON access_method.oid = operator_class.opcmethod
        WHERE operator_class.opcname = 'gin_trgm_ops'
          AND access_method.amname = 'gin'
    ) OR NOT EXISTS (
        SELECT 1
        FROM pg_opclass AS operator_class
        JOIN pg_am AS access_method ON access_method.oid = operator_class.opcmethod
        WHERE operator_class.opcname = 'gist_trgm_ops'
          AND access_method.amname = 'gist'
    ) OR to_regprocedure('similarity(text,text)') IS NULL THEN
        RAISE EXCEPTION
            'pg_trgm is required and must expose similarity, gin_trgm_ops, and gist_trgm_ops'
            USING ERRCODE = '55000';
    END IF;
END;
$$
"""


def upgrade() -> None:
    """Assert infrastructure capability, then create only project-owned indexes."""
    op.execute(PG_TRGM_CAPABILITY_ASSERTION)
    op.execute(
        "CREATE INDEX ix_translation_keys_search_product_scope_deleted "
        "ON translation_keys (product_id, scope_id, is_deleted, id)"
    )
    op.execute(
        "CREATE INDEX ix_translation_keys_search_raw_key_pattern "
        "ON translation_keys "
        "((replace(lower(raw_key), 'ß', 'ss') COLLATE \"C\") text_pattern_ops, id)"
    )
    op.execute(
        "CREATE INDEX ix_translation_keys_search_raw_key_trgm "
        "ON translation_keys USING gin (replace(lower(raw_key), 'ß', 'ss') gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_translation_values_search_scope_filters "
        "ON translation_values "
        "(scope_id, language, review_state, is_deleted, is_over_limit, "
        "effective_max_chars, translation_key_id, id)"
    )
    op.execute(
        "CREATE INDEX ix_translation_values_search_source_text_trgm "
        "ON translation_values USING gin "
        "(replace(lower(source_text), 'ß', 'ss') gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_translation_values_search_display_text_trgm "
        "ON translation_values USING gin "
        "(replace(lower(display_text), 'ß', 'ss') gin_trgm_ops)"
    )


def downgrade() -> None:
    """Drop exactly the six search indexes owned by this revision."""
    op.drop_index(
        "ix_translation_values_search_display_text_trgm",
        table_name="translation_values",
    )
    op.drop_index(
        "ix_translation_values_search_source_text_trgm",
        table_name="translation_values",
    )
    op.drop_index(
        "ix_translation_values_search_scope_filters",
        table_name="translation_values",
    )
    op.drop_index(
        "ix_translation_keys_search_raw_key_trgm",
        table_name="translation_keys",
    )
    op.drop_index(
        "ix_translation_keys_search_raw_key_pattern",
        table_name="translation_keys",
    )
    op.drop_index(
        "ix_translation_keys_search_product_scope_deleted",
        table_name="translation_keys",
    )
