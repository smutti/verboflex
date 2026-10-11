"""Import-time coverage snapshots for the product workspace."""

import sqlalchemy as sa

from alembic import op

revision = "0043_product_workspace_coverage"
down_revision = "0042_pull_request_tracking"
branch_labels = None
depends_on = None

WHITESPACE = (
    " \t\n\r\v\f\x1c\x1d\x1e\x1f\x85\xa0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)


def _guard(add: bool) -> None:
    definition = op.get_bind().scalar(
        sa.text(
            "SELECT pg_get_functiondef('verboflex_guard_localization_scope_activation'::regproc)"
        )
    )
    old = "- 'language_counts'"
    new = old + " - 'coverage_snapshot'"
    op.execute(definition.replace(old, new) if add else definition.replace(new, old))


def upgrade() -> None:
    op.execute("ALTER TABLE localization_scopes ADD COLUMN coverage_snapshot jsonb")
    # Like language_counts, coverage is read metadata, never activation authority.
    _guard(True)
    op.execute(f"""
    CREATE FUNCTION verboflex_scope_coverage(scope_uuid uuid, base_language text)
    RETURNS jsonb LANGUAGE sql STABLE AS $coverage$
    WITH groups AS MATERIALIZED (
        SELECT key.id, value.language,
            bool_or(value.source_text IS NOT NULL) AS has_source,
            bool_and(value.translated_text IS NOT NULL
                AND btrim(value.translated_text, '{WHITESPACE}') <> ''
                AND NOT value.structure @>
                    '[{{"kind":"qt_ts:translation",
                        "fields":[{{"name":"status","value":"unfinished"}}]}}]'::jsonb
            ) AS complete
        FROM translation_keys key
        JOIN translation_values value
          ON value.translation_key_id=key.id AND value.scope_id=key.scope_id
        WHERE key.scope_id=scope_uuid AND NOT key.is_deleted AND NOT value.is_deleted
          AND key.product_id=(SELECT product_id FROM localization_scopes WHERE id=scope_uuid)
        GROUP BY key.id, value.language
    ), sources AS (
        SELECT DISTINCT id FROM groups WHERE has_source
    ), targets AS (
        SELECT DISTINCT language FROM groups WHERE language <> base_language
    ), languages AS (
        SELECT DISTINCT language FROM groups
        UNION SELECT base_language
        WHERE base_language IS NOT NULL AND EXISTS (SELECT 1 FROM sources)
    )
    SELECT jsonb_build_object(
        'source_string_count', (SELECT count(*) FROM sources),
        'expected_translation_count',
            (SELECT count(*) FROM sources) * (SELECT count(*) FROM targets),
        'translated_count', (SELECT count(*) FROM groups JOIN sources USING(id)
                             WHERE language <> base_language AND complete),
        'languages', coalesce((SELECT jsonb_agg(language ORDER BY language) FROM languages),
                              '[]'::jsonb)
    )
    $coverage$
    """)
    op.execute("""
        UPDATE localization_scopes scope
        SET coverage_snapshot=verboflex_scope_coverage(scope.id, mapping.base_language),
            read_version=scope.read_version+1
        FROM product_repository_mappings mapping
        WHERE mapping.id=scope.current_mapping_id AND scope.active_execution_id IS NOT NULL
    """)


def downgrade() -> None:
    _guard(False)
    op.execute("DROP FUNCTION verboflex_scope_coverage(uuid, text)")
    op.execute("ALTER TABLE localization_scopes DROP COLUMN coverage_snapshot")
