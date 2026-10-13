"""Key-first multilingual reads in one consistent PostgreSQL snapshot.

Two bounded result sets: language/authority metadata, then at most 51 key summaries
with selected aggregates. No detail fan-out or provider calls enter this boundary.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from verboflex.auth.product_access import visible_product_sql
from verboflex.schemas.translation_workspace import (
    TranslationKeyPageResponse,
    TranslationKeySearchQuery,
    TranslationKeySummary,
    TranslationLanguageSlot,
)
from verboflex.schemas.translations import TranslationLanguageOptionResponse
from verboflex.services.product_summary import _WHITESPACE
from verboflex.services.signed_cursor import InvalidSignedCursor, SignedCursorCodec
from verboflex.services.translation_search import (
    _SOURCE_COMPARISON_SQL,
    _SOURCE_RECORDS_SQL,
    InvalidTranslationCursor,
    escape_like_literal,
    language_label,
    normalize_search_query,
)

_CURRENT = f"""
    SELECT scope.id AS scope_id, product.id AS product_id, product.display_name AS product_name,
           scope.current_revision_id, scope.active_execution_id, scope.dataset_version,
           scope.read_version, scope.language_counts,
           mapping.base_language
    FROM products AS product
    JOIN localization_scopes AS scope ON scope.product_id = product.id
        AND scope.current_revision_id = product.active_revision_id
        AND scope.active_execution_id IS NOT NULL
    JOIN product_repository_mappings AS mapping ON mapping.id = scope.current_mapping_id
        AND mapping.revision_id = scope.current_revision_id
    WHERE {visible_product_sql()} AND product.is_active AND product.deleted_at IS NULL
      AND (CAST(:product_id AS uuid) IS NULL OR product.id = :product_id)
"""

# Scope epochs and language counters are maintained by statement-level database
# triggers in the same transaction as each write. Reads never hash all proposals
# or revisions, and repeatable read keeps the epoch and page in one snapshot.
_METADATA = text(f"""
WITH current AS ({_CURRENT}), language_candidates AS (
    SELECT counts.key AS code, counts.key = current.base_language AS is_base
    FROM current JOIN localization_scopes scope ON scope.id=current.scope_id
    CROSS JOIN LATERAL jsonb_each(scope.language_counts) counts
    WHERE (counts.value->>0)::bigint > 0
    UNION ALL
    SELECT current.base_language, true
    FROM current JOIN localization_scopes scope ON scope.id=current.scope_id
    WHERE current.base_language IS NOT NULL AND EXISTS (
        SELECT 1 FROM jsonb_each(scope.language_counts) counts
        WHERE (counts.value->>1)::bigint > 0
    )
), languages AS (
    SELECT code, bool_or(is_base) AS is_base FROM language_candidates GROUP BY code
    ORDER BY bool_or(is_base) DESC, code COLLATE "C" LIMIT 501
)
SELECT coalesce((SELECT jsonb_agg(code ORDER BY is_base DESC, code COLLATE "C")
                 FROM languages), '[]') AS languages,
       md5(coalesce((SELECT jsonb_agg(to_jsonb(current) ORDER BY scope_id)
           FROM current), '[]'::jsonb)::text) AS authority
""")

# Imported and pending predicates remain separate. Only complete, current pending
# membership may replace text; one member from another scope/language fails closed.
_KEY_PAGE = text(rf"""
WITH current AS ({_CURRENT}), aggregates AS MATERIALIZED (
    SELECT key.id AS key_id, current.scope_id, current.product_id, current.product_name,
        key.raw_key, casefold(key.raw_key COLLATE pg_unicode_fast) COLLATE "C" AS stable_key,
        current.base_language, value.language,
        (SELECT member.id FROM translation_values AS member
         WHERE member.translation_key_id = key.id AND member.scope_id = current.scope_id
           AND member.language = value.language ORDER BY member.id LIMIT 1) AS group_id,
        (array_agg(value.id ORDER BY value.id))[1] AS display_value_id,
        count(*)::integer AS value_count,
        array_agg(DISTINCT value.selector_kind ORDER BY value.selector_kind) AS selector_kinds,
        array_agg(DISTINCT value.review_state ORDER BY value.review_state) AS states,
        count(*) FILTER (WHERE value.is_over_limit)::integer AS over_limit_count,
        count(*) FILTER (WHERE value.effective_max_chars IS NOT NULL AND NOT value.is_over_limit)
            ::integer AS within_limit_count,
        count(*) FILTER (WHERE value.effective_max_chars IS NULL)::integer AS no_max_count,
        bool_and(key.is_deleted OR value.is_deleted) AS is_deleted,
        bool_or(key.is_deleted OR value.is_deleted) AS has_deleted,
        bool_or((:deleted <> 'active' OR NOT value.is_deleted) AND
            (CAST(:state AS text) IS NULL OR value.review_state = :state)) AS state_matches,
        bool_or((:deleted <> 'active' OR NOT value.is_deleted) AND (
            CAST(:violation AS text) IS NULL
            OR (:violation = 'over_limit' AND value.is_over_limit)
            OR (:violation = 'within_limit' AND value.effective_max_chars IS NOT NULL
                AND NOT value.is_over_limit)
            OR (:violation = 'no_max' AND value.effective_max_chars IS NULL))) AS limit_matches,
        bool_or(NOT value.is_deleted AND
            btrim(coalesce(value.translated_text, ''), :whitespace) = '') AS imported_empty,
        bool_or(source_projection.source_changed) AS source_changed,
        (array_agg(source_projection.source_text ORDER BY value.is_deleted, value.id)
            FILTER (WHERE source_projection.source_text IS NOT NULL))[1] AS source_text,
        bool_or(source_projection.source_truncated) AS source_truncated,
        bool_or(source_projection.exact_match) AS source_exact,
        bool_or(source_projection.prefix_match) AS source_prefix,
        bool_or(source_projection.partial_match) AS source_partial,
        bool_or((:deleted <> 'active' OR NOT value.is_deleted) AND
            casefold(value.display_text COLLATE pg_unicode_fast) = :query) AS text_exact,
        bool_or((:deleted <> 'active' OR NOT value.is_deleted) AND
            casefold(value.display_text COLLATE pg_unicode_fast) LIKE :prefix ESCAPE '\')
            AS text_prefix,
        bool_or((:deleted <> 'active' OR NOT value.is_deleted) AND
            casefold(value.display_text COLLATE pg_unicode_fast) LIKE :partial ESCAPE '\')
            AS text_partial,
        (array_agg(left(value.display_text, 1024) ORDER BY value.is_deleted, value.id))[1]
            AS imported_text,
        bool_or(length(value.display_text) > 1024) AS imported_truncated,
        bool_or(locator.repository_side = 'keys') AS keys_side,
        bool_and(coalesce(locator.value_id IS NOT NULL
            AND locator.import_execution_id = current.active_execution_id, false)) AS provenance_ok,
        bool_and(coalesce(locator.format IN ('android_xml', 'json', 'ios_strings', 'qt_ts'), false))
            AS format_ok,
        bool_and(coalesce(
            (locator.format = 'android_xml' AND value.selector_kind IN
                ('scalar', 'android_quantity', 'android_array_item'))
            OR (locator.format = 'json' AND value.selector_kind IN ('json_path', 'scalar'))
            OR (locator.format = 'ios_strings' AND value.selector_kind = 'scalar')
            OR (locator.format = 'qt_ts' AND value.translated_text IS NOT NULL
                AND value.selector_kind IN ('scalar', 'qt_numerus', 'qt_length_variant')),
            false)) AND NOT bool_or(EXISTS (
                SELECT 1 FROM jsonb_array_elements(value.structure) AS node
                WHERE locator.format = 'android_xml' AND node->>'kind' = 'android_xml:inline'
            )) AND NOT bool_or((
                SELECT count(*) > 1 FROM jsonb_array_elements(value.structure) AS node
                WHERE locator.format = 'android_xml'
                  AND node->>'kind' IN ('android_xml:text', 'android_xml:tail', 'android_xml:cdata')
            )) AS shape_ok,
        bool_and(locator.repository_side IN ('direct', 'translations')
            AND locator.format IN ('android_xml', 'json', 'ios_strings')
            AND value.source_text IS NOT NULL AND value.translated_text IS NULL) AS source_leaf,
        bool_and(value.translated_text IS NOT NULL) AS translation_leaf
    FROM current
    JOIN translation_keys AS key
      ON key.scope_id = current.scope_id AND key.product_id = current.product_id
    JOIN translation_values AS value
      ON value.translation_key_id = key.id AND value.scope_id = current.scope_id
    LEFT JOIN translation_value_locators AS locator
      ON locator.value_id = value.id AND locator.translation_key_id = key.id
    LEFT JOIN LATERAL (
        SELECT key.id AS key_id, current.scope_id, value.language, current.base_language,
               (key.is_deleted OR value.is_deleted) AS is_deleted,
               (:deleted <> 'active' AND CAST(:work_status AS text) IS NULL)
                 AS include_deleted_embedded
    ) AS source_anchor ON true
    LEFT JOIN LATERAL (
        SELECT (array_agg(left(source.resolved_text, 1024) ORDER BY source.id))[1] AS source_text,
            bool_or(length(source.resolved_text) > 1024) AS source_truncated,
            bool_or(casefold(source.resolved_text COLLATE pg_unicode_fast) = :query) AS exact_match,
            bool_or(casefold(source.resolved_text COLLATE pg_unicode_fast)
                LIKE :prefix ESCAPE '\') AS prefix_match,
            bool_or(casefold(source.resolved_text COLLATE pg_unicode_fast)
                LIKE :partial ESCAPE '\') AS partial_match,
            bool_or((comparison.comparison->>'changed')::boolean) AS source_changed
        FROM ({_SOURCE_RECORDS_SQL}) AS source
        LEFT JOIN LATERAL ({_SOURCE_COMPARISON_SQL}) AS comparison ON true
    ) AS source_projection ON true
    WHERE (:deleted <> 'active' OR (NOT key.is_deleted AND NOT value.is_deleted))
      /* candidate_keys */
    GROUP BY key.id, current.scope_id, current.product_id, current.product_name,
             current.base_language, value.language
), effective AS MATERIALIZED (
    SELECT aggregate.*, proposal.version AS pending_version, proposal.state AS pending_state,
        pending.value_count AS pending_value_count,
        pending.over_limit_count AS pending_over_limit_count,
        (proposal.reconciliation_required OR NOT coalesce(pending.fresh, false))
            AS pending_reconciliation_required,
        (proposal.state <> 'rejected' AND NOT proposal.reconciliation_required
            AND coalesce(pending.fresh, false)) AS use_pending,
        pending.first_text AS pending_text, pending.text_truncated AS pending_truncated,
        CASE WHEN proposal.state <> 'rejected' AND NOT proposal.reconciliation_required
            AND pending.fresh THEN pending.empty ELSE aggregate.imported_empty END AS empty,
        CASE WHEN proposal.state <> 'rejected' AND NOT proposal.reconciliation_required
            AND pending.fresh THEN pending.exact_match ELSE aggregate.text_exact END AS exact_match,
        CASE WHEN proposal.state <> 'rejected' AND NOT proposal.reconciliation_required
            AND pending.fresh THEN pending.prefix_match ELSE aggregate.text_prefix END
                AS prefix_match,
        CASE WHEN proposal.state <> 'rejected' AND NOT proposal.reconciliation_required
            AND pending.fresh THEN pending.partial_match ELSE aggregate.text_partial END
                AS partial_match
    FROM aggregates AS aggregate
    LEFT JOIN translation_proposals AS proposal
      ON proposal.translation_key_id = aggregate.key_id AND proposal.language = aggregate.language
    LEFT JOIN LATERAL (
        SELECT count(*)::integer AS value_count,
            count(*) FILTER (WHERE member.effective_max_chars IS NOT NULL
                AND pending.grapheme_count > member.effective_max_chars)
                ::integer AS over_limit_count,
            count(*) = aggregate.value_count AND bool_and(coalesce(
                member.id IS NOT NULL AND NOT member.is_deleted
                AND latest.revision_number = pending.basis_revision_number
                AND latest.revision_digest = pending.basis_digest, false)) AS fresh,
            (array_agg(left(pending.proposed_text, 1024) ORDER BY member.id))[1] AS first_text,
            bool_or(length(pending.proposed_text) > 1024) AS text_truncated,
            bool_or(btrim(pending.proposed_text, :whitespace) = '') AS empty,
            bool_or(casefold(pending.proposed_text COLLATE pg_unicode_fast) = :query)
                AS exact_match,
            bool_or(casefold(pending.proposed_text COLLATE pg_unicode_fast)
                LIKE :prefix ESCAPE '\') AS prefix_match,
            bool_or(casefold(pending.proposed_text COLLATE pg_unicode_fast)
                LIKE :partial ESCAPE '\') AS partial_match
        FROM translation_proposal_values AS pending
        LEFT JOIN translation_values AS member ON member.id = pending.translation_value_id
          AND member.translation_key_id = aggregate.key_id AND member.scope_id = aggregate.scope_id
          AND member.language = aggregate.language
          AND member.selector_version = pending.selector_version
          AND member.selector_digest = pending.selector_digest
        LEFT JOIN LATERAL (
            SELECT revision_number, revision_digest FROM translation_value_revisions
            WHERE value_id = member.id ORDER BY revision_number DESC LIMIT 1
        ) AS latest ON true
        WHERE pending.proposal_id = proposal.id
    ) AS pending ON proposal.id IS NOT NULL
), ranked AS MATERIALIZED (
    SELECT effective.*,
        CASE WHEN NOT :has_query THEN 3
            WHEN stable_key = :query OR source_exact OR exact_match THEN 0
            WHEN stable_key LIKE :prefix ESCAPE '\' OR source_prefix OR prefix_match THEN 1
            ELSE 2 END AS rank,
        coalesce((NOT :has_query OR stable_key LIKE :partial ESCAPE '\'
            OR source_partial OR partial_match)
          AND (:deleted = 'all' OR (:deleted = 'active' AND NOT is_deleted)
               OR (:deleted = 'deleted' AND is_deleted))
          AND state_matches AND limit_matches
          AND (CAST(:work_status AS text) IS NULL OR (
            NOT has_deleted AND base_language IS NOT NULL AND language <> base_language AND (
                (:work_status = 'needs_translation' AND empty)
                OR (:work_status = 'needs_review' AND pending_state = 'draft'
                    AND NOT pending_reconciliation_required)
                OR (:work_status = 'source_changed' AND source_changed)))), false) AS matches
    FROM effective
), contexts AS MATERIALIZED (
    SELECT key_id, scope_id, min(base_language) AS language,
        (array_agg(source_text ORDER BY is_deleted, language)
            FILTER (WHERE source_text IS NOT NULL))[1] AS source_text,
        bool_or(source_truncated) AS source_truncated,
        coalesce(bool_or(NOT :has_query OR stable_key LIKE :partial ESCAPE '\'
            OR source_partial), false) AS text_matches,
        bool_and(is_deleted) AS is_deleted,
        CASE WHEN NOT :has_query THEN 3
            WHEN bool_or(stable_key = :query OR source_exact) THEN 0
            WHEN bool_or(stable_key LIKE :prefix ESCAPE '\' OR source_prefix) THEN 1
            ELSE 2 END AS rank,
        coalesce(bool_or(NOT :has_query OR stable_key LIKE :partial ESCAPE '\' OR source_partial)
            AND CAST(:state AS text) IS NULL AND CAST(:violation AS text) IS NULL
            AND CAST(:work_status AS text) IS NULL
            AND (:deleted = 'all' OR (:deleted = 'active' AND NOT bool_and(is_deleted))
                OR (:deleted = 'deleted' AND bool_and(is_deleted))), false) AS matches
    FROM ranked GROUP BY key_id, scope_id
    HAVING bool_or(source_text IS NOT NULL)
), absent_matches AS MATERIALIZED (
    -- A missing target has no value identity. Match it through its live source
    -- and this scope's supported locales, without inventing a group or state.
    SELECT context.key_id, context.scope_id, language.code AS language, context.rank
    FROM contexts AS context
    JOIN current ON current.scope_id = context.scope_id
    CROSS JOIN LATERAL unnest(CASE WHEN CAST(:language AS text) IS NOT NULL
        THEN ARRAY[CAST(:language AS text)] ELSE CAST(:languages AS text[]) END) AS language(code)
    WHERE :work_status = 'needs_translation' AND :deleted <> 'deleted'
      AND CAST(:state AS text) IS NULL AND CAST(:violation AS text) IS NULL
      AND context.text_matches AND NOT context.is_deleted
      AND language.code <> context.language
      AND coalesce((current.language_counts->language.code->>0)::bigint, 0) > 0
      -- Retained deleted values remain tombstones, not newly absent work.
      AND NOT EXISTS (
          SELECT 1 FROM translation_values AS existing
          WHERE existing.translation_key_id = context.key_id
            AND existing.scope_id = context.scope_id AND existing.language = language.code
      )
), matching AS (
    SELECT key_id, scope_id, min(rank) AS rank FROM (
        SELECT key_id, scope_id, rank FROM ranked
        WHERE matches AND ((CAST(:language AS text) IS NOT NULL AND language = :language)
            OR (CAST(:language AS text) IS NULL AND language = ANY(:languages)))
        UNION ALL
        SELECT context.key_id, context.scope_id, context.rank FROM contexts AS context
        WHERE context.matches AND ((CAST(:language AS text) IS NOT NULL AND language = :language)
            OR (CAST(:language AS text) IS NULL AND language = ANY(:languages)))
          AND NOT EXISTS (SELECT 1 FROM ranked AS imported WHERE imported.key_id=context.key_id
                AND imported.scope_id=context.scope_id AND imported.language=context.language)
        UNION ALL
        SELECT key_id, scope_id, rank FROM absent_matches
    ) AS matches GROUP BY key_id, scope_id
), ordered AS (
    SELECT matching.*, casefold(key.raw_key COLLATE pg_unicode_fast) COLLATE "C" AS stable_key
    FROM matching JOIN translation_keys AS key
      ON key.id = matching.key_id AND key.scope_id = matching.scope_id
), anchor AS (
    SELECT * FROM ordered WHERE key_id = :last_id AND rank = :last_rank
), page AS (
    SELECT * FROM ordered WHERE NOT :has_cursor OR (rank, stable_key, key_id) >
        (SELECT rank, stable_key, key_id FROM anchor)
    ORDER BY rank, stable_key, key_id LIMIT 51
)
SELECT validity.valid, page.key_id, page.scope_id, page.rank,
       left(key.raw_key, 1024) AS raw_key, length(key.raw_key) > 1024 AS key_truncated,
       current.product_id, current.product_name, current.base_language,
       context.source_text, coalesce(context.source_truncated, false) AS source_truncated,
       coalesce(slots.items, '[]') AS slots
FROM (SELECT NOT :has_cursor OR EXISTS(SELECT 1 FROM anchor) AS valid) AS validity
LEFT JOIN page ON true
LEFT JOIN translation_keys AS key ON key.id=page.key_id AND key.scope_id=page.scope_id
LEFT JOIN current ON current.scope_id=page.scope_id AND current.product_id=key.product_id
LEFT JOIN contexts AS context ON context.key_id=page.key_id AND context.scope_id=page.scope_id
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object(
        'language', language.code, 'kind', CASE WHEN slot.group_id IS NOT NULL THEN 'imported'
            WHEN language.code = context.language THEN 'source_context' ELSE 'absent' END,
        'group_id', slot.group_id,
        'matches_filters', (CAST(:language AS text) IS NULL OR language.code = :language)
            AND (coalesce(slot.matches, language.code = context.language AND context.matches, false)
                OR EXISTS (SELECT 1 FROM absent_matches AS missing
                    WHERE missing.key_id = page.key_id AND missing.scope_id = page.scope_id
                      AND missing.language = language.code)),
        'effective_text', CASE WHEN slot.group_id IS NULL THEN
            CASE WHEN language.code=context.language THEN context.source_text END
            WHEN slot.use_pending THEN slot.pending_text ELSE slot.imported_text END,
        'text_truncated', coalesce(CASE WHEN slot.group_id IS NULL THEN
            language.code=context.language AND context.source_truncated
            WHEN slot.use_pending THEN slot.pending_truncated
            ELSE slot.imported_truncated END, false),
        'preview_kind', CASE WHEN slot.value_count > 1 THEN 'aggregate'
            WHEN slot.group_id IS NOT NULL THEN 'scalar'
            WHEN language.code=context.language THEN 'context' ELSE 'absent' END,
        'value_count', coalesce(slot.value_count, 0),
        'selector_kinds', coalesce(slot.selector_kinds, ARRAY[]::text[]),
        'states', coalesce(slot.states, ARRAY[]::text[]),
        'pending_change', CASE WHEN slot.pending_version IS NULL THEN NULL ELSE jsonb_build_object(
            'version', slot.pending_version, 'state', slot.pending_state,
            'reconciliation_required', slot.pending_reconciliation_required,
            'value_count', slot.pending_value_count) END,
        'comment_count', (SELECT count(*) FROM translation_comments AS comment
            WHERE comment.translation_key_id=slot.key_id AND comment.language=slot.language
              AND comment.deleted_at IS NULL),
        'over_limit_count', coalesce(slot.over_limit_count, 0),
        'effective_over_limit_count', coalesce(CASE WHEN slot.use_pending
            THEN slot.pending_over_limit_count ELSE slot.over_limit_count END, 0),
        'within_limit_count', coalesce(slot.within_limit_count, 0),
        'no_max_count', coalesce(slot.no_max_count, 0),
        'is_deleted', CASE WHEN slot.group_id IS NOT NULL THEN slot.is_deleted
            WHEN language.code = context.language THEN context.is_deleted ELSE false END,
        'source_changed', coalesce(slot.source_changed, false),
        'provenance', CASE WHEN locator.value_id IS NULL THEN NULL ELSE jsonb_build_object(
            'repository_side', locator.repository_side, 'format', locator.format,
            'repository_name', left(coalesce(repository.descriptive_name,
                repository.workspace || '/' || repository.repository_slug), 1024),
            'branch', left(locator.configured_branch, 1024), 'path', left(locator.path, 1024),
            'path_truncated', length(locator.path) > 1024) END,
        'editable', capability.reason IS NULL,
        'read_only_reason', capability.reason,
        'edit_field', CASE WHEN capability.reason IS NOT NULL THEN NULL
            WHEN slot.source_leaf THEN 'source_text' ELSE 'translated_text' END
    ) ORDER BY language.position) AS items
    FROM unnest(CAST(:languages AS text[])) WITH ORDINALITY AS language(code, position)
    LEFT JOIN ranked AS slot ON slot.key_id=page.key_id AND slot.scope_id=page.scope_id
        AND slot.language=language.code
    LEFT JOIN translation_value_locators AS locator
        ON locator.value_id=slot.display_value_id AND locator.translation_key_id=slot.key_id
    LEFT JOIN repositories AS repository ON repository.id=locator.repository_id
    LEFT JOIN LATERAL (
        SELECT CASE WHEN slot.group_id IS NULL THEN CASE WHEN language.code=context.language
                THEN 'source_context' ELSE 'absent' END
            WHEN slot.has_deleted THEN 'deleted'
            WHEN slot.keys_side THEN 'keys_repository'
            WHEN NOT slot.provenance_ok THEN 'unavailable_provenance'
            WHEN NOT slot.format_ok THEN 'unsupported_format'
            WHEN NOT slot.shape_ok OR slot.value_count > 10000 THEN 'unsupported_shape'
            WHEN NOT (slot.source_leaf OR slot.translation_leaf) THEN 'mixed_edit_fields'
            ELSE NULL END AS reason
    ) AS capability ON true
    -- The selection is shared across products; supported locales belong to this scope.
    -- Reuse transactional counters instead of scanning sibling keys for every slot.
    WHERE (slot.group_id IS NOT NULL OR language.code = context.language
        OR coalesce((current.language_counts->language.code->>0)::bigint, 0) > 0
        OR (language.code = current.base_language AND EXISTS (
            SELECT 1 FROM jsonb_each(current.language_counts) counts
            WHERE (counts.value->>1)::bigint > 0
        )))
      AND (:deleted <> 'active' OR slot.group_id IS NOT NULL
        OR language.code = context.language OR NOT EXISTS (
            SELECT 1 FROM translation_values AS removed
            WHERE removed.translation_key_id=page.key_id AND removed.scope_id=page.scope_id
              AND removed.language=language.code AND removed.is_deleted
        ))
) AS slots ON page.key_id IS NOT NULL
ORDER BY page.rank, page.stable_key, page.key_id
""")


# With no content/work predicates, choose the bounded page from current key/value
# identities before computing previews, proposal state and provenance. Keep the
# cursor anchor in the candidate window so the normal validity check still runs.
_BROWSE_CANDIDATES = """
, browse_candidates AS MATERIALIZED (
    SELECT candidate.id FROM current
    CROSS JOIN LATERAL (
        SELECT key.id, casefold(key.raw_key COLLATE pg_unicode_fast) COLLATE "C" AS stable_key
        FROM translation_keys key
        WHERE key.scope_id=current.scope_id AND key.product_id=current.product_id
          AND NOT key.is_deleted AND (
            NOT :has_cursor OR (
                left(casefold(key.raw_key COLLATE pg_unicode_fast), 256) COLLATE "C" >= (
                    SELECT left(casefold(anchor.raw_key COLLATE pg_unicode_fast), 256) COLLATE "C"
                    FROM translation_keys anchor WHERE anchor.id=:last_id
                ) AND (casefold(key.raw_key COLLATE pg_unicode_fast) COLLATE "C", key.id) >= (
                    SELECT casefold(anchor.raw_key COLLATE pg_unicode_fast) COLLATE "C", anchor.id
                    FROM translation_keys anchor WHERE anchor.id=:last_id
                )
            )
          ) AND EXISTS (
            SELECT 1 FROM translation_values member
            WHERE member.translation_key_id=key.id AND member.scope_id=current.scope_id
              AND NOT member.is_deleted AND (
                (CAST(:language AS text) IS NOT NULL AND member.language=:language)
                OR (CAST(:language AS text) IS NULL AND member.language=ANY(:languages))
                OR (member.source_text IS NOT NULL AND (
                    (CAST(:language AS text) IS NOT NULL AND current.base_language=:language)
                    OR (CAST(:language AS text) IS NULL AND current.base_language=ANY(:languages))
                ))
              )
          )
        ORDER BY left(casefold(key.raw_key COLLATE pg_unicode_fast), 256) COLLATE "C",
            casefold(key.raw_key COLLATE pg_unicode_fast) COLLATE "C", key.id
        LIMIT 52
    ) candidate
    ORDER BY candidate.stable_key, candidate.id LIMIT 52
)
"""
_BROWSE_PAGE = text(
    _KEY_PAGE.text.replace(
        "), aggregates AS MATERIALIZED (",
        ")" + _BROWSE_CANDIDATES + ", aggregates AS MATERIALIZED (",
        1,
    ).replace("/* candidate_keys */", "AND key.id IN (SELECT id FROM browse_candidates)")
)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def search_translation_keys(
    session: Session,
    *,
    principal_id: UUID,
    query: TranslationKeySearchQuery,
    cursor_secret: str,
) -> TranslationKeyPageResponse:
    """Require a fresh read session, sharing authority and rows in repeatable read."""
    if session.in_transaction():
        raise RuntimeError("key search requires a fresh read session")
    session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
    # Compilation dominates these short indexed reads; do not alter pooled or
    # server defaults. PostgreSQL restores this setting on commit and rollback.
    session.execute(text("SET LOCAL jit = off"))
    metadata = (
        session.execute(_METADATA, {"product_id": query.product_id, "principal_id": principal_id})
        .mappings()
        .one()
    )
    available = metadata["languages"]
    languages = query.visible_languages if query.visible_languages is not None else available[:20]
    normalized = normalize_search_query(query.q)
    filters = query.model_dump(exclude={"cursor", "visible_languages", "q"})
    filters.update(q=normalized, visible_languages=sorted(languages))
    binding = _digest([principal_id, filters, metadata["authority"]])
    codec = SignedCursorCodec(cursor_secret, max_cursor_chars=2048)
    last_id = UUID(int=0)
    last_rank = 3
    if query.cursor is not None:
        try:
            payload = codec.decode_payload(
                query.cursor, required_keys=frozenset({"v", "binding", "last"})
            )
            last = payload["last"]
            if (
                payload["v"] != "translation-keys:2"
                or payload["binding"] != binding
                or not isinstance(last, list)
                or len(last) != 2
                or type(last[0]) is not int
                or last[0] not in (0, 1, 2, 3)
                or not isinstance(last[1], str)
                or str(UUID(last[1])) != last[1]
            ):
                raise ValueError
            last_rank, last_id = last[0], UUID(last[1])
        except (InvalidSignedCursor, ValueError, TypeError) as error:
            raise InvalidTranslationCursor("invalid translation cursor") from error
    literal = escape_like_literal(normalized or "")
    parameters = {
        "principal_id": principal_id,
        **query.model_dump(exclude={"cursor", "visible_languages", "q", "page_size"}),
        "languages": languages,
        "query": normalized or "",
        "has_query": normalized is not None,
        "prefix": literal + "%",
        "partial": "%" + literal + "%",
        "whitespace": _WHITESPACE,
        "has_cursor": query.cursor is not None,
        "last_id": last_id,
        "last_rank": last_rank,
    }
    browse = (
        normalized is None
        and query.deleted == "active"
        and query.state is None
        and query.violation is None
        and query.work_status is None
    )
    rows = session.execute(_BROWSE_PAGE if browse else _KEY_PAGE, parameters).mappings().all()
    if not rows[0]["valid"]:
        raise InvalidTranslationCursor("invalid translation cursor")
    found = [row for row in rows if row["key_id"] is not None]
    items = []
    for row in found[:50]:
        slots = [
            TranslationLanguageSlot.model_validate(
                {
                    **slot,
                    "language_label": language_label(slot["language"]),
                }
            )
            for slot in row["slots"]
        ]
        data: dict[str, Any] = dict(row)
        for field in ("valid", "key_id", "slots"):
            del data[field]
        items.append(
            TranslationKeySummary(
                **data,
                translation_key_id=row["key_id"],
                slots=slots,
            )
        )
    next_cursor = None
    if len(found) > 50:
        last_row = found[49]
        next_cursor = codec.encode_payload(
            {
                "v": "translation-keys:2",
                "binding": binding,
                "last": [last_row["rank"], str(last_row["key_id"])],
            }
        )
    return TranslationKeyPageResponse(
        items=items,
        next_cursor=next_cursor,
        visible_languages=languages,
        available_languages=[
            TranslationLanguageOptionResponse(code=code, label=language_label(code))
            for code in available[:500]
        ],
        default_selection_capped=query.visible_languages is None and len(available) > 20,
        available_languages_truncated=len(available) > 500,
    )
