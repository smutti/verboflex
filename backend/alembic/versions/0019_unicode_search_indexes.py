"""Align search indexes with PostgreSQL Unicode case folding.

Revision ID: 0019_unicode_search_indexes
Revises: 0018_constraint_generation
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019_unicode_search_indexes"
down_revision: str | None = "0018_constraint_generation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_case_indexes() -> None:
    for table, suffix in (
        ("translation_keys", "raw_key_pattern"),
        ("translation_keys", "raw_key_trgm"),
        ("translation_values", "source_text_trgm"),
        ("translation_values", "display_text_trgm"),
    ):
        op.drop_index(f"ix_{table}_search_{suffix}", table_name=table)


def upgrade() -> None:
    # pg_unicode_fast is built into PostgreSQL 18; no extension or locale installation.
    op.execute("SELECT casefold('ﬀ' COLLATE pg_unicode_fast)")
    _drop_case_indexes()
    op.execute(
        "CREATE INDEX ix_translation_keys_search_raw_key_pattern ON translation_keys "
        '((left(casefold(raw_key COLLATE pg_unicode_fast), 256) COLLATE "C") '
        "text_pattern_ops, id)"
    )
    for table, column, expression in (
        ("translation_keys", "raw_key", "raw_key"),
        ("translation_values", "source_text", "coalesce(source_text, '')"),
        ("translation_values", "display_text", "display_text"),
    ):
        op.execute(
            f"CREATE INDEX ix_{table}_search_{column}_trgm ON {table} USING gin "
            f"(casefold({expression} COLLATE pg_unicode_fast) gin_trgm_ops)"
        )


def downgrade() -> None:
    _drop_case_indexes()
    op.execute(
        "CREATE INDEX ix_translation_keys_search_raw_key_pattern ON translation_keys "
        "((replace(lower(raw_key), 'ß', 'ss') COLLATE \"C\") text_pattern_ops, id)"
    )
    for table, column in (
        ("translation_keys", "raw_key"),
        ("translation_values", "source_text"),
        ("translation_values", "display_text"),
    ):
        op.execute(
            f"CREATE INDEX ix_{table}_search_{column}_trgm ON {table} USING gin "
            f"(replace(lower({column}), 'ß', 'ss') gin_trgm_ops)"
        )
