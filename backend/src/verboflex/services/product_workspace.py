"""Product-card reads over import-time snapshots, independent of corpus size."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from verboflex.auth.product_access import visible_product_sql
from verboflex.schemas.product_workspace import ProductWorkspacePage, ProductWorkspaceQuery
from verboflex.services.translation_search import escape_like_literal, normalize_search_query

PAGE_SIZE = 24

_WORKSPACE_SQL = text(f"""
WITH filtered AS MATERIALIZED (
    SELECT id, display_name, name_key, active_revision_id
    FROM products
    WHERE is_active AND deleted_at IS NULL AND {visible_product_sql("products.id")}
      AND (CAST(:product_id AS uuid) IS NULL OR id=CAST(:product_id AS uuid))
      AND (CAST(:query AS text) IS NULL OR name_key LIKE :pattern ESCAPE '\\')
), page AS (
    SELECT * FROM filtered ORDER BY name_key COLLATE "C", id
    LIMIT :limit OFFSET :offset
), cards AS (
    SELECT page.id, page.display_name AS name, stats.*,
        (SELECT count(*) FROM product_repository_mappings mapping
         WHERE mapping.revision_id=page.active_revision_id
           AND NOT EXISTS (SELECT 1 FROM localization_scopes scope
               WHERE scope.product_id=page.id AND scope.current_mapping_id=mapping.id
                 AND scope.active_execution_id IS NOT NULL)) AS unimported_scope_count
    FROM page
    LEFT JOIN LATERAL (
        WITH scopes AS MATERIALIZED (
            SELECT scope.coverage_snapshot AS snapshot, execution.finished_at
            FROM localization_scopes scope
            JOIN import_executions execution ON execution.id=scope.active_execution_id
            WHERE scope.product_id=page.id AND page.active_revision_id IS NOT NULL
              AND execution.state='succeeded'
        ), totals AS (
            SELECT count(*) AS imported_scope_count, max(finished_at) AS last_imported_at,
                bool_and(snapshot IS NOT NULL) AS available,
                coalesce(sum((snapshot->>'source_string_count')::bigint),0) AS source_count,
                coalesce(sum((snapshot->>'expected_translation_count')::bigint),0) AS expected,
                coalesce(sum((snapshot->>'translated_count')::bigint),0) AS translated
            FROM scopes
        ), languages AS (
            SELECT DISTINCT language COLLATE "C" AS language
            FROM scopes CROSS JOIN LATERAL jsonb_array_elements_text(snapshot->'languages') language
        )
        SELECT imported_scope_count, last_imported_at,
            CASE WHEN available THEN jsonb_build_object(
                'source_string_count', source_count,
                'expected_translation_count', expected,
                'translated_count', translated,
                'missing_count', expected-translated,
                'coverage_percent', CASE WHEN expected=0 THEN NULL
                    WHEN translated=expected THEN 100.0
                    ELSE least(99.9, round(100.0*translated/expected,1)) END,
                'language_count', (SELECT count(*) FROM languages),
                'languages', coalesce((SELECT jsonb_agg(language ORDER BY language)
                    FROM (SELECT language FROM languages ORDER BY language LIMIT 6) preview),
                    '[]'::jsonb)
            ) END AS coverage
        FROM totals
    ) stats ON true
)
SELECT (SELECT count(*) FROM filtered) AS total,
       coalesce(jsonb_agg(to_jsonb(cards) ORDER BY page.name_key COLLATE "C", page.id)
         FILTER (WHERE cards.id IS NOT NULL), '[]'::jsonb) AS items
FROM page LEFT JOIN cards USING(id)
""")


def list_product_workspaces(
    session: Session, *, query: ProductWorkspaceQuery, principal_id: UUID
) -> ProductWorkspacePage:
    normalized = normalize_search_query(query.q)
    row = (
        session.execute(
            _WORKSPACE_SQL,
            {
                "query": normalized,
                "principal_id": principal_id,
                "product_id": query.product_id,
                "pattern": f"%{escape_like_literal(normalized or '')}%",
                "limit": PAGE_SIZE,
                "offset": (query.page - 1) * PAGE_SIZE,
            },
        )
        .mappings()
        .one()
    )
    return ProductWorkspacePage(
        items=row["items"],
        total=row["total"],
        page=query.page,
        has_more=query.page * PAGE_SIZE < row["total"],
    )
