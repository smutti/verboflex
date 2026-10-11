"""Transactional scope metadata instead of corpus-wide read fingerprints."""

import sqlalchemy as sa

from alembic import op

revision = "0034_workspace_read_projection"
down_revision = "0033_repository_providers"
branch_labels = None
depends_on = None

TABLES = {
    "translation_keys": True,
    "translation_values": True,
    "translation_proposals": True,
    "translation_constraints": True,
    "translation_proposal_values": False,
    "translation_value_revisions": False,
    "translation_value_locators": False,
}
EPOCH_GUARD = """
    IF TG_OP = 'UPDATE' AND NEW.read_version = OLD.read_version + 1
       AND (to_jsonb(NEW) - 'read_version' - 'language_counts')
         = (to_jsonb(OLD) - 'read_version' - 'language_counts')
    THEN RETURN NEW; END IF;
"""


def _catalog() -> None:
    # Maintenance verifies these definitions before deleting protected evidence.
    op.execute("""UPDATE maintenance_schema SET installed_definition = (
        SELECT coalesce(jsonb_agg(jsonb_build_array(tgrelid::regclass::text,
            tgname, pg_get_triggerdef(oid)) ORDER BY tgrelid::regclass::text, tgname),
            '[]'::jsonb)::text FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN
            (SELECT oid FROM pg_class WHERE relnamespace='public'::regnamespace)
        ) WHERE name='triggers'""")


def upgrade() -> None:
    op.execute("""ALTER TABLE localization_scopes
        ADD COLUMN read_version bigint NOT NULL DEFAULT 0 CHECK (read_version >= 0),
        ADD COLUMN language_counts jsonb NOT NULL DEFAULT '{}'::jsonb
            CHECK (jsonb_typeof(language_counts)='object')""")
    definition = op.get_bind().scalar(
        sa.text(
            "SELECT pg_get_functiondef('verboflex_guard_localization_scope_activation'::regproc)"
        )
    )
    op.execute(definition.replace("BEGIN", "BEGIN\n" + EPOCH_GUARD, 1))
    op.execute("""UPDATE localization_scopes s SET read_version=read_version+1,
        language_counts=coalesce((SELECT jsonb_object_agg(language, counts)
          FROM (SELECT language, jsonb_build_array(count(*),
              count(*) FILTER (WHERE source_text IS NOT NULL)) counts
            FROM translation_values WHERE scope_id=s.id GROUP BY language) q), '{}'::jsonb)""")
    for table, direct in TABLES.items():
        for event in ("insert", "update", "delete"):
            relations = []
            if event != "insert":
                relations.append(("old_rows", -1))
            if event != "delete":
                relations.append(("new_rows", 1))
            referencing = " ".join(
                f"{'OLD' if sign == -1 else 'NEW'} TABLE AS {name}" for name, sign in relations
            )
            if table == "translation_values":
                changed = " UNION ALL ".join(
                    f"SELECT scope_id, language, {sign}::bigint AS n, "
                    f"{sign} * (source_text IS NOT NULL)::int AS source_n FROM {name}"
                    for name, sign in relations
                )
                body = f"""
                FOR changed IN WITH deltas AS ({changed})
                    SELECT scope_id, jsonb_object_agg(language, counts) AS counts
                    FROM (SELECT scope_id, language,
                        jsonb_build_array(sum(n), sum(source_n)) counts
                        FROM deltas GROUP BY scope_id, language) grouped
                    GROUP BY scope_id ORDER BY scope_id
                LOOP
                    UPDATE localization_scopes scope
                    SET read_version=scope.read_version+1,
                        language_counts=coalesce((
                            SELECT jsonb_object_agg(language, jsonb_build_array(n, source_n))
                            FROM (SELECT language, sum(n) n, sum(source_n) source_n FROM (
                                SELECT key language, (value->>0)::bigint n,
                                    (value->>1)::bigint source_n
                                FROM jsonb_each(scope.language_counts)
                                UNION ALL
                                SELECT key, (value->>0)::bigint, (value->>1)::bigint
                                FROM jsonb_each(changed.counts)
                            ) pieces GROUP BY language) merged WHERE n > 0
                        ), '{{}}'::jsonb)
                    WHERE scope.id=changed.scope_id;
                END LOOP;
                """
            else:
                changed = " UNION ".join(
                    f"SELECT scope_id FROM {name}"
                    if direct
                    else f"SELECT k.scope_id FROM {name} r "
                    "JOIN translation_keys k ON k.id=r.translation_key_id"
                    for name, _ in relations
                )
                body = f"""
                FOR changed IN SELECT DISTINCT scope_id FROM ({changed}) scopes ORDER BY scope_id
                LOOP
                    UPDATE localization_scopes SET read_version=read_version+1
                    WHERE id=changed.scope_id;
                END LOOP;
                """
            function = f"verboflex_read_{table}_{event}"
            op.execute(f"""CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$
                DECLARE changed record;
                BEGIN {body} RETURN NULL; END $$""")
            op.execute(f"""CREATE TRIGGER trg_read_{event} AFTER {event.upper()} ON {table}
                REFERENCING {referencing} FOR EACH STATEMENT EXECUTE FUNCTION {function}()""")
    # Bounded prefixes fit a B-tree even for 65K-character provider keys. The read
    # orders by prefix, complete folded key, UUID, preserving exact lexical order.
    op.execute("""CREATE INDEX ix_translation_keys_live_browse ON translation_keys
        (scope_id, (left(casefold(raw_key COLLATE pg_unicode_fast), 256) COLLATE "C"))
        WHERE NOT is_deleted""")
    op.execute("""CREATE INDEX ix_translation_values_retired ON translation_values
        (scope_id, translation_key_id, language, id) WHERE is_deleted""")
    _catalog()


def downgrade() -> None:
    for table in TABLES:
        for event in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER trg_read_{event} ON {table}")
            op.execute(f"DROP FUNCTION verboflex_read_{table}_{event}()")
    definition = op.get_bind().scalar(
        sa.text(
            "SELECT pg_get_functiondef('verboflex_guard_localization_scope_activation'::regproc)"
        )
    )
    op.execute(definition.replace(EPOCH_GUARD, ""))
    op.execute(
        "ALTER TABLE localization_scopes DROP COLUMN read_version, DROP COLUMN language_counts"
    )
    op.drop_index("ix_translation_keys_live_browse")
    op.drop_index("ix_translation_values_retired")
    _catalog()
