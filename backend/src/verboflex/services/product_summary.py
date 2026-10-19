"""Read-only coverage of configured sources and their retained successful imports."""

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from verboflex.schemas.admin_products import AdminProductSummaryResponse
from verboflex.services.products import ProductNotFound

LANGUAGE_LIMIT = 500
# Python's Unicode whitespace set, explicitly including separators not covered
# consistently by database locales. Do not strip or hydrate source text in Python.
_WHITESPACE = (
    " \t\n\r\v\f\x1c\x1d\x1e\x1f\x85\xa0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)
_QT_UNFINISHED = json.dumps(
    [{"kind": "qt_ts:translation", "fields": [{"name": "status", "value": "unfinished"}]}]
)

# Keep retained baselines only while their repository/branch identity is configured.
_ACTIVE_MAPPING_SQL = """EXISTS (
    SELECT 1 FROM product_repository_mappings AS active_mapping
    WHERE active_mapping.revision_id = product.active_revision_id
      AND active_mapping.identity_key = scope.mapping_identity_key
)"""

_SUMMARY_SQL = text(f"""
WITH product AS (
    SELECT id, active_revision_id FROM products
    WHERE id = :product_id AND deleted_at IS NULL
), imported_scopes AS (
    SELECT scope.id, scope.current_mapping_id, mapping.base_language, execution.finished_at
    FROM product
    JOIN localization_scopes AS scope ON scope.product_id = product.id
    JOIN product_revisions AS revision
      ON revision.id = scope.current_revision_id AND revision.product_id = product.id
    JOIN product_repository_mappings AS mapping
      ON mapping.id = scope.current_mapping_id AND mapping.revision_id = revision.id
     AND mapping.identity_key = scope.mapping_identity_key
    JOIN import_jobs AS job
      ON job.id = scope.active_import_job_id AND job.product_id = product.id
     AND job.mapping_id = mapping.id AND job.revision_id = revision.id
    JOIN import_executions AS execution
      ON execution.id = scope.active_execution_id AND execution.import_job_id = job.id
    WHERE product.active_revision_id IS NOT NULL AND execution.state = 'succeeded'
      AND {_ACTIVE_MAPPING_SQL}
), live_groups AS (
    SELECT scope.id AS scope_id, key.id AS key_id, value.language, scope.base_language,
           bool_or(value.source_text IS NOT NULL) AS has_source,
           bool_and(value.translated_text IS NOT NULL
                    AND btrim(value.translated_text, :whitespace) <> ''
                    AND NOT value.structure @> CAST(:qt_unfinished AS jsonb)) AS complete
    FROM imported_scopes AS scope
    JOIN translation_keys AS key
      ON key.scope_id = scope.id AND key.product_id = :product_id AND NOT key.is_deleted
    JOIN translation_values AS value
      ON value.translation_key_id = key.id AND value.scope_id = scope.id
     AND NOT value.is_deleted
    GROUP BY scope.id, key.id, value.language, scope.base_language
), source_keys AS (
    SELECT DISTINCT scope_id, key_id FROM live_groups WHERE has_source
), source_counts AS (
    SELECT scope_id, count(*) AS source_count FROM source_keys GROUP BY scope_id
), scope_languages AS (
    SELECT DISTINCT scope_id, language FROM live_groups WHERE language <> base_language
), completed_groups AS (
    SELECT groups.scope_id, groups.language, count(*) AS translated_count
    FROM live_groups AS groups
    JOIN source_keys AS source USING (scope_id, key_id)
    WHERE groups.language <> groups.base_language AND groups.complete
    GROUP BY groups.scope_id, groups.language
), language_counts AS (
    SELECT language.language, sum(coalesce(source.source_count, 0))::bigint AS expected_count,
           sum(coalesce(complete.translated_count, 0))::bigint AS translated_count
    FROM scope_languages AS language
    LEFT JOIN source_counts AS source USING (scope_id)
    LEFT JOIN completed_groups AS complete USING (scope_id, language)
    GROUP BY language.language
), language_coverage AS (
    SELECT *, expected_count - translated_count AS missing_count,
           round(100.0 * translated_count / nullif(expected_count, 0), 2) AS coverage_percent
    FROM language_counts
), totals AS (
    SELECT count(*) AS target_language_count,
           coalesce(sum(expected_count), 0)::bigint AS expected_translation_count,
           coalesce(sum(translated_count), 0)::bigint AS translated_count,
           coalesce(sum(missing_count), 0)::bigint AS missing_count
    FROM language_coverage
), bounded_languages AS (
    SELECT * FROM language_coverage
    ORDER BY missing_count DESC, coverage_percent ASC NULLS FIRST, language ASC
    LIMIT :language_limit
)
SELECT product.id AS product_id,
       (SELECT count(*) FROM source_keys) AS source_string_count,
       totals.*,
       round(100.0 * totals.translated_count
             / nullif(totals.expected_translation_count, 0), 2) AS coverage_percent,
       (SELECT count(*) FROM imported_scopes) AS imported_scope_count,
       (SELECT count(*) FROM product_repository_mappings AS mapping
        WHERE mapping.revision_id = product.active_revision_id
          AND NOT EXISTS (SELECT 1 FROM imported_scopes AS scope
                          WHERE scope.current_mapping_id = mapping.id)) AS unimported_scope_count,
       (SELECT max(finished_at) FROM imported_scopes) AS last_imported_at,
       coalesce((SELECT jsonb_agg(to_jsonb(coverage_row)
                    ORDER BY missing_count DESC, coverage_percent ASC NULLS FIRST, language ASC)
                 FROM bounded_languages AS coverage_row), '[]'::jsonb) AS languages,
       totals.target_language_count > :language_limit AS languages_has_more
FROM product CROSS JOIN totals
""")


def get_product_summary(session: Session, *, product_id: UUID) -> AdminProductSummaryResponse:
    """Aggregate missing rows without materializing the key/language Cartesian product.

    Each observed scope/language gets the entire scope's source-key denominator.
    Only complete existing groups contribute to the numerator. The table bound
    never truncates aggregate totals. Retained baselines survive failed refreshes.
    """
    row = (
        session.execute(
            _SUMMARY_SQL,
            {
                "product_id": product_id,
                "whitespace": _WHITESPACE,
                "qt_unfinished": _QT_UNFINISHED,
                "language_limit": LANGUAGE_LIMIT,
            },
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ProductNotFound("product unavailable")
    return AdminProductSummaryResponse.model_validate(dict(row))
