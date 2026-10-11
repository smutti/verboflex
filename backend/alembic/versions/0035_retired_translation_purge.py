"""Permit exact retired-content deletion while preserving live evidence guards."""

import sqlalchemy as sa

from alembic import op

revision = "0035_retired_translation_purge"
down_revision = "0034_workspace_read_projection"
branch_labels = None
depends_on = None

GUARDS = (
    "verboflex_guard_translation_value_revision_immutable",
    "verboflex_guard_review_evidence_immutable",
    "verboflex_guard_canonical_staging",
)
EXCEPTION = """
    IF TG_OP = 'DELETE' AND verboflex_retired_content_delete_allowed(TG_TABLE_NAME, to_jsonb(OLD))
    THEN RETURN OLD; END IF;
"""

ALLOW = """
CREATE FUNCTION verboflex_retired_content_delete_allowed(tab text, row_data jsonb)
RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE key_id uuid; locale text;
BEGIN
    IF tab = 'staged_translation_values' THEN
        RETURN EXISTS (
            SELECT 1 FROM import_executions e
            WHERE e.id=(row_data->>'import_execution_id')::uuid
              AND e.state IN ('succeeded', 'failed')
              AND NOT EXISTS (SELECT 1 FROM import_rewrite_proposals r
                  WHERE r.proposed_execution_id=e.id AND r.status='pending')
        );
    END IF;
    IF tab = 'translation_value_revisions' THEN
        RETURN EXISTS (SELECT 1 FROM translation_values v
            JOIN translation_keys k ON k.id=v.translation_key_id
            WHERE v.id=(row_data->>'value_id')::uuid AND (v.is_deleted OR k.is_deleted));
    END IF;
    IF tab = 'translation_comment_mentions' THEN
        SELECT v.translation_key_id, v.language INTO key_id, locale
        FROM translation_comment_versions v WHERE v.id=(row_data->>'comment_version_id')::uuid;
    ELSIF tab IN ('translation_comment_versions', 'review_activities') THEN
        key_id := (row_data->>'translation_key_id')::uuid;
        locale := row_data->>'language';
    ELSE RETURN false;
    END IF;
    RETURN EXISTS (SELECT 1 FROM translation_keys k WHERE k.id=key_id AND (
        k.is_deleted OR (
            EXISTS (SELECT 1 FROM translation_values v
                WHERE v.translation_key_id=k.id AND v.language=locale AND v.is_deleted)
            AND (tab='review_activities' OR NOT EXISTS (
                SELECT 1 FROM translation_values v
                WHERE v.translation_key_id=k.id AND v.language=locale AND NOT v.is_deleted
            ))
        )
    ));
END $$
"""


def _refresh_guard_catalog(name: str) -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE maintenance_schema SET installed_definition="
            "pg_get_functiondef(to_regproc(:name)) WHERE name=:name"
        ),
        {"name": name},
    )


def upgrade() -> None:
    op.execute(ALLOW)
    for name in GUARDS:
        definition = op.get_bind().scalar(
            sa.text("SELECT pg_get_functiondef(to_regproc(:name))"), {"name": name}
        )
        op.execute(definition.replace("BEGIN", "BEGIN\n" + EXCEPTION, 1))
        _refresh_guard_catalog(name)


def downgrade() -> None:
    for name in GUARDS:
        definition = op.get_bind().scalar(
            sa.text("SELECT pg_get_functiondef(to_regproc(:name))"), {"name": name}
        )
        op.execute(definition.replace(EXCEPTION, ""))
        _refresh_guard_catalog(name)
    op.execute("DROP FUNCTION verboflex_retired_content_delete_allowed(text, jsonb)")
