"""Bounded, authorization-safe search over exact active localization datasets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from verboflex.auth.product_access import visible_product_sql
from verboflex.localization.graphemes import grapheme_count
from verboflex.services.product_summary import _WHITESPACE
from verboflex.services.signed_cursor import InvalidSignedCursor, SignedCursorCodec

SEARCH_PAGE_SIZE = 50
MAX_SEARCH_QUERY_CHARS = 256
MAX_CURSOR_CHARS = 2048
CURSOR_VERSION = 2
MAX_OPTION_COUNT = 500
MAX_GROUP_VALUE_COUNT = 10_000
_ZERO_UUID = UUID(int=0)
_AUTHORIZED_ACTIVE_PRODUCTS_SQL = (
    "SELECT id, display_name, name_key FROM products "
    "WHERE is_active AND deleted_at IS NULL /* product_access */"
)

DeletedMode = Literal["active", "deleted", "all"]
StateFilter = Literal["draft", "approved", "rejected"]
ViolationFilter = Literal["over_limit", "within_limit", "no_max"]
WorkStatus = Literal["needs_translation", "needs_review", "source_changed"]
SourceResolution = Literal["embedded", "matched", "unmatched", "ambiguous", "unavailable"]
StateSummary = StateFilter | Literal["mixed"]
ConstraintSource = Literal["none", "base_default", "language_override"]
ConstraintStatus = Literal["no_max", "within_limit", "over_limit"]
SelectorKind = Literal[
    "scalar",
    "android_quantity",
    "android_array_item",
    "qt_numerus",
    "qt_length_variant",
    "json_path",
]
RepositorySide = Literal["direct", "keys", "translations"]
LocalizationFormat = Literal["android_xml", "qt_ts", "json", "ios_strings", "xliff"]


class TranslationSearchInputError(ValueError):
    """Raised when a direct service caller exceeds a public search bound."""


class InvalidTranslationCursor(ValueError):
    """Raised for every malformed, tampered, replayed, or stale cursor."""


@dataclass(frozen=True, slots=True)
class TranslationSearchFilters:
    """Canonical closed search scope included verbatim in cursor authority."""

    query: str | None = None
    product_id: UUID | None = None
    language: str | None = None
    state: StateFilter | None = None
    violation: ViolationFilter | None = None
    work_status: WorkStatus | None = None
    deleted: DeletedMode = "active"
    page_size: int = SEARCH_PAGE_SIZE

    def __post_init__(self) -> None:
        object.__setattr__(self, "query", normalize_search_query(self.query))
        if self.language is not None and not 1 <= len(self.language) <= 64:
            raise TranslationSearchInputError("language is outside its allowed bound")
        if self.state not in (None, "draft", "approved", "rejected"):
            raise TranslationSearchInputError("state is invalid")
        if self.violation not in (None, "over_limit", "within_limit", "no_max"):
            raise TranslationSearchInputError("violation is invalid")
        if self.work_status not in (None, "needs_translation", "needs_review", "source_changed"):
            raise TranslationSearchInputError("work status is invalid")
        if self.deleted not in ("active", "deleted", "all"):
            raise TranslationSearchInputError("deleted mode is invalid")
        if self.page_size != SEARCH_PAGE_SIZE:
            raise TranslationSearchInputError("page size must be 50")


@dataclass(frozen=True, slots=True)
class TranslationSummaryProvenance:
    """One bounded last-known locator, not all of a group's source locations."""

    repository_name: str
    branch: str
    path: str


@dataclass(frozen=True, slots=True)
class PendingTranslationSummary:
    """Compact pending aggregate state attached to one search result."""

    version: int
    state: StateFilter
    reconciliation_required: bool
    value_count: int


@dataclass(frozen=True, slots=True)
class TranslationGroupSummary:
    """One raw-key plus language group without selector loss."""

    id: UUID
    product_id: UUID
    product_name: str
    raw_key: str
    language: str
    rank: int
    source_text: str | None
    source_language: str | None
    translated_text: str | None
    selector_kinds: tuple[SelectorKind, ...]
    provenance: TranslationSummaryProvenance | None
    value_count: int
    over_limit_count: int
    within_limit_count: int
    no_max_count: int
    states: tuple[StateFilter, ...]
    state_summary: StateSummary
    has_over_limit: bool
    has_no_max: bool
    is_deleted: bool
    pending_change: PendingTranslationSummary | None
    comment_count: int


@dataclass(frozen=True, slots=True)
class TranslationSearchPage:
    """One exact 50-group keyset page."""

    items: tuple[TranslationGroupSummary, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class TranslationProductOption:
    """One active product available to every current authenticated principal."""

    id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class TranslationLanguageOption:
    """One exact canonical dataset language with a server-owned label."""

    code: str
    label: str


@dataclass(frozen=True, slots=True)
class TranslationOptions:
    """Current server-ordered search filter choices."""

    products: tuple[TranslationProductOption, ...]
    languages: tuple[TranslationLanguageOption, ...]


@dataclass(frozen=True, slots=True)
class TranslationConstraintProjection:
    """Materialized current maximum-length result for one exact value."""

    actual: int
    maximum: int | None
    source: ConstraintSource
    status: ConstraintStatus
    overage: int | None


@dataclass(frozen=True, slots=True)
class TranslationProvenance:
    """Credential-free current source locator from the active execution."""

    repository_id: UUID
    repository_name: str
    repository_side: RepositorySide
    branch: str
    path: str
    format: LocalizationFormat
    commit_hash: str
    execution_id: UUID
    line: int | None
    column: int | None


@dataclass(frozen=True, slots=True)
class TranslationValueDetail:
    """One individually addressable selector value without flattening structure."""

    id: UUID
    selector_version: Literal[1]
    selector_kind: SelectorKind
    selector_digest: str
    selector_fields: tuple[dict[str, object], ...] | None
    history: tuple[dict[str, object], ...]
    history_has_more: bool
    source_text: str | None
    translated_text: str | None
    display_text: str
    structure: tuple[object, ...]
    review_state: StateFilter
    grapheme_count: int
    constraint: TranslationConstraintProjection
    is_deleted: bool
    deleted_at: datetime | None
    provenance: TranslationProvenance | None
    source_value_id: UUID | None = None
    source_resolution: SourceResolution | None = None
    source_comparison: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class PendingTranslationValueDetail:
    """One pending selector with current server-derived validation."""

    translation_value_id: UUID
    selector_version: Literal[1]
    selector_digest: str
    basis_revision_number: int
    basis_digest: str
    text: str
    grapheme_count: int
    maximum: int | None
    is_over_limit: bool
    approval_eligible: bool
    submission_eligible: bool


@dataclass(frozen=True, slots=True)
class PendingTranslationDetail:
    """Complete pending aggregate shown beside its published values."""

    version: int
    state: StateFilter
    reconciliation_required: bool
    updated_by: UUID
    updated_at: datetime
    values: tuple[PendingTranslationValueDetail, ...]


@dataclass(frozen=True, slots=True)
class TranslationGroupDetail:
    """Complete active-dataset projection for one opaque group UUID."""

    id: UUID
    product_id: UUID
    product_name: str
    raw_key: str
    language: str
    states: tuple[StateFilter, ...]
    state_summary: StateSummary
    is_deleted: bool
    values: tuple[TranslationValueDetail, ...]
    base_language: str | None
    explicit_maximum: int | None
    constraint_version: int | None
    base_maximum: int | None
    pending_change: PendingTranslationDetail | None
    comment_count: int
    mutation_eligible: bool
    review_eligible: bool
    source_context: tuple[dict[str, object], ...] | None = None


class TranslationGroupUnavailable(LookupError):
    """Bounded missing-or-inaccessible group result."""


@dataclass(frozen=True, slots=True)
class _CursorPosition:
    rank: int
    language: str
    group_id: UUID


def normalize_search_query(query: str | None) -> str | None:
    """Collapse whitespace and casefold without broadening an empty query."""
    if query is None:
        return None
    normalized = " ".join(query.split())
    if not normalized:
        return None
    if len(normalized) > MAX_SEARCH_QUERY_CHARS:
        raise TranslationSearchInputError("query is outside its allowed bound")
    return normalized.casefold()


def escape_like_literal(value: str) -> str:
    """Escape PostgreSQL LIKE metacharacters in the required order."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _canonical_filter(filters: TranslationSearchFilters) -> dict[str, object]:
    result: dict[str, object] = {
        "deleted": filters.deleted,
        "language": filters.language,
        "page_size": filters.page_size,
        "product_id": str(filters.product_id) if filters.product_id is not None else None,
        "query": filters.query,
        "state": filters.state,
        "violation": filters.violation,
    }
    if filters.work_status is not None:
        result["work_status"] = filters.work_status
    return result


def _scoped(statement: TextClause, principal_id: UUID) -> TextClause:
    return text(
        statement.text.replace(
            "/* product_access */", "AND " + visible_product_sql("products.id", ":access_actor")
        )
    ).bindparams(access_actor=principal_id)


def _scope_digest(
    session: Session,
    *,
    principal_id: UUID,
    filters: TranslationSearchFilters | None = None,
) -> str:
    rows = session.execute(
        _scoped(
            text(
                "SELECT product.id AS product_id, scope.id AS scope_id, "
                "scope.active_execution_id, scope.dataset_version "
                f"FROM ({_AUTHORIZED_ACTIVE_PRODUCTS_SQL}) AS product "
                "JOIN localization_scopes AS scope ON scope.product_id = product.id "
                "WHERE scope.active_execution_id IS NOT NULL "
                "ORDER BY product.id, scope.id "
                "FOR SHARE OF product, scope"
            ),
            principal_id,
        )
    ).mappings()
    authority = {
        "principal_id": str(principal_id),
        "scopes": [
            [
                str(row["product_id"]),
                str(row["scope_id"]),
                str(row["active_execution_id"]),
                row["dataset_version"],
            ]
            for row in rows
        ],
    }
    if filters is not None and filters.work_status is not None:
        proposals = session.execute(
            _scoped(
                text(f"""
            SELECT proposal.id, proposal.version, proposal.state, proposal.reconciliation_required
            FROM ({_AUTHORIZED_ACTIVE_PRODUCTS_SQL}) AS product
            JOIN localization_scopes AS scope ON scope.product_id = product.id
              AND scope.active_execution_id IS NOT NULL
            JOIN translation_keys AS key ON key.scope_id = scope.id AND key.product_id = product.id
            JOIN translation_proposals AS proposal ON proposal.translation_key_id = key.id
            WHERE (CAST(:product_id AS uuid) IS NULL OR product.id = :product_id)
              AND (CAST(:language AS text) IS NULL OR proposal.language = :language)
            ORDER BY proposal.id
        """),
                principal_id,
            ),
            {"product_id": filters.product_id, "language": filters.language},
        ).all()
        authority["proposals"] = [list(map(str, row)) for row in proposals]
    encoded = json.dumps(authority, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _encode_cursor(
    *,
    scope_digest: str,
    filters: TranslationSearchFilters,
    position: _CursorPosition,
    cursor_secret: str,
) -> str:
    payload = {
        "filters": _filter_digest(filters),
        "last": [
            position.rank,
            position.language,
            str(position.group_id),
        ],
        "scope": scope_digest,
        "v": CURSOR_VERSION,
    }
    # Only caller: SQL rank 0..3, persisted ASCII locale, UUID, and two SHA256
    # digests. Even maximum permitted fields stay below 512 wire characters;
    # untrusted incoming cursors retain the independent 2048-character guard.
    return SignedCursorCodec(cursor_secret, max_cursor_chars=MAX_CURSOR_CHARS).encode_payload(
        payload
    )


def _filter_digest(filters: TranslationSearchFilters) -> str:
    """Bound cursor size independently of Unicode expansion in filter values."""
    body = json.dumps(_canonical_filter(filters), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def _decode_cursor(
    cursor: str,
    *,
    scope_digest: str,
    filters: TranslationSearchFilters,
    cursor_secret: str,
) -> _CursorPosition:
    if not 1 <= len(cursor) <= MAX_CURSOR_CHARS:
        raise InvalidTranslationCursor("invalid translation cursor")
    try:
        payload = SignedCursorCodec(
            cursor_secret, max_cursor_chars=MAX_CURSOR_CHARS
        ).decode_payload(
            cursor,
            required_keys=frozenset(("filters", "last", "scope", "v")),
        )
        if payload["v"] != CURSOR_VERSION:
            raise ValueError
        if payload["scope"] != scope_digest:
            raise ValueError
        if payload["filters"] != _filter_digest(filters):
            raise ValueError
        last = payload["last"]
        if not isinstance(last, list) or len(last) != 3:
            raise ValueError
        if type(last[0]) is not int or last[0] not in (0, 1, 2, 3):
            raise ValueError
        if not isinstance(last[1], str) or not 1 <= len(last[1]) <= 64:
            raise ValueError
        if not isinstance(last[2], str) or str(UUID(last[2])) != last[2]:
            raise ValueError
        position = _CursorPosition(
            rank=last[0],
            language=last[1],
            group_id=UUID(last[2]),
        )
        return position
    except (InvalidSignedCursor, TypeError, ValueError) as error:
        raise InvalidTranslationCursor("invalid translation cursor") from error


# A source anchor is always derived from an authorized exact logical key/scope.
# Embedded source wins; split formats use that key's configured base language.
# This shared selection drives list matching, work queues and detailed context.
_SOURCE_RECORDS_SQL = """
    SELECT source.*,
           CASE WHEN source.language = source_anchor.language
                AND source.source_text IS NOT NULL THEN 'embedded' ELSE 'base_language' END
               AS origin,
           coalesce(source.source_text, source.translated_text) AS resolved_text
    FROM translation_values AS source
    WHERE source.scope_id = source_anchor.scope_id
      AND source.translation_key_id = source_anchor.key_id
      AND (NOT source.is_deleted OR (
          source_anchor.include_deleted_embedded
          AND source.language = source_anchor.language AND source.source_text IS NOT NULL
      ))
      AND (NOT source_anchor.is_deleted OR (
          source_anchor.include_deleted_embedded
          AND source.language = source_anchor.language AND source.source_text IS NOT NULL
      ))
      AND (
          (source.language = source_anchor.language AND source.source_text IS NOT NULL)
          OR (source.language = source_anchor.base_language AND NOT EXISTS (
              SELECT 1 FROM translation_values AS embedded
              WHERE embedded.scope_id = source_anchor.scope_id
                AND embedded.translation_key_id = source_anchor.key_id
                AND embedded.language = source_anchor.language
                AND NOT embedded.is_deleted AND embedded.source_text IS NOT NULL
          ))
      )
"""

_SOURCE_COMPARISON_SQL = """
    SELECT CASE WHEN NOT source.is_deleted AND NOT source_anchor.is_deleted
        AND count(*) = 2 AND count(content) = 2 AND NOT bool_or(is_deleted)
        THEN jsonb_build_object(
            'source_value_id', source.id, 'origin', source.origin,
            'previous_revision_number',
                (array_agg(revision_number ORDER BY revision_number DESC))[2],
            'current_revision_number',
                (array_agg(revision_number ORDER BY revision_number DESC))[1],
            'changed', (array_agg(content ORDER BY revision_number DESC))[1]
                       <> (array_agg(content ORDER BY revision_number DESC))[2],
            'previous_text', left((array_agg(content ORDER BY revision_number DESC))[2], 4096),
            'current_text', left((array_agg(content ORDER BY revision_number DESC))[1], 4096),
            'previous_truncated',
                length((array_agg(content ORDER BY revision_number DESC))[2]) > 4096,
            'current_truncated',
                length((array_agg(content ORDER BY revision_number DESC))[1]) > 4096,
            'previous_commit_hash',
                (array_agg(source_commit_hash ORDER BY revision_number DESC))[2],
            'current_commit_hash', (array_agg(source_commit_hash ORDER BY revision_number DESC))[1],
            'previous_execution_id',
                (array_agg(import_execution_id ORDER BY revision_number DESC))[2],
            'current_execution_id',
                (array_agg(import_execution_id ORDER BY revision_number DESC))[1]
        ) ELSE NULL END AS comparison
    FROM (
        SELECT revision_number, source_commit_hash, import_execution_id, is_deleted,
               CASE WHEN source.origin = 'embedded' THEN source_text
                    ELSE coalesce(source_text, translated_text) END AS content
        FROM translation_value_revisions WHERE value_id = source.id
        ORDER BY revision_number DESC LIMIT 2
    ) AS revisions
"""

_SEARCH_SQL = text(
    rf"""
WITH authorized_products AS (
    {_AUTHORIZED_ACTIVE_PRODUCTS_SQL}
), raw_grouped AS (
    SELECT
        (array_agg(value.id ORDER BY value.id))[1] AS group_id,
        key.id AS key_id,
        key.product_id,
        product.display_name AS product_name,
        key.raw_key,
        scope.current_mapping_id AS mapping_id,
        scope.id AS scope_id,
        mapping.base_language,
        casefold(key.raw_key COLLATE pg_unicode_fast) COLLATE "C" AS stable_key,
        value.language,
        CASE
            WHEN NOT :has_query THEN 3
            WHEN bool_or(
                (:deleted <> 'active' OR NOT value.is_deleted) AND (
                casefold(key.raw_key COLLATE pg_unicode_fast)
                    = casefold(:query COLLATE pg_unicode_fast)
                OR source_projection.exact_match
                OR casefold(value.display_text COLLATE pg_unicode_fast)
                    = casefold(:query COLLATE pg_unicode_fast)
                )
            ) THEN 0
            WHEN bool_or(
                (:deleted <> 'active' OR NOT value.is_deleted) AND (
                casefold(key.raw_key COLLATE pg_unicode_fast)
                    LIKE casefold(:prefix COLLATE pg_unicode_fast) ESCAPE '\'
                OR source_projection.prefix_match
                OR casefold(value.display_text COLLATE pg_unicode_fast)
                    LIKE casefold(:prefix COLLATE pg_unicode_fast) ESCAPE '\'
                )
            ) THEN 1
            ELSE 2
        END AS rank,
        (array_agg(source_projection.source_text ORDER BY value.is_deleted, value.id))[1]
            AS source_text,
        bool_or(source_projection.source_changed) AS source_changed,
        bool_or(NOT value.is_deleted AND
            (value.translated_text IS NULL OR btrim(value.translated_text, :whitespace) = ''))
            AS needs_translation,
        (array_agg(value.translated_text ORDER BY value.is_deleted, value.id)
            FILTER (WHERE value.translated_text IS NOT NULL))[1] AS translated_text,
        count(*)::integer AS value_count,
        array_agg(DISTINCT value.selector_kind ORDER BY value.selector_kind) AS selector_kinds,
        count(*) FILTER (WHERE value.is_over_limit)::integer AS over_limit_count,
        count(*) FILTER (
            WHERE value.effective_max_chars IS NOT NULL AND NOT value.is_over_limit
        )::integer AS within_limit_count,
        count(*) FILTER (WHERE value.effective_max_chars IS NULL)::integer AS no_max_count,
        array_agg(DISTINCT value.review_state ORDER BY value.review_state) AS states,
        bool_or(value.is_over_limit) AS has_over_limit,
        bool_or(value.effective_max_chars IS NULL) AS has_no_max,
        bool_and(key.is_deleted OR value.is_deleted) AS is_deleted
    FROM authorized_products AS product
    JOIN localization_scopes AS scope
      ON scope.product_id = product.id
     AND scope.active_execution_id IS NOT NULL
    JOIN translation_keys AS key
      ON key.scope_id = scope.id
     AND key.product_id = product.id
    JOIN translation_values AS value
      ON value.scope_id = scope.id
     AND value.translation_key_id = key.id
    LEFT JOIN product_repository_mappings AS mapping ON mapping.id = scope.current_mapping_id
    LEFT JOIN LATERAL (
        SELECT key.id AS key_id, scope.id AS scope_id,
               value.language AS language, mapping.base_language,
               (key.is_deleted OR value.is_deleted) AS is_deleted,
               (:deleted <> 'active' AND CAST(:work_status AS text) IS NULL)
                   AS include_deleted_embedded
    ) AS source_anchor ON true
    LEFT JOIN LATERAL (
        SELECT (array_agg(source.resolved_text ORDER BY source.id))[1] AS source_text,
            bool_or(casefold(source.resolved_text COLLATE pg_unicode_fast)
                = casefold(:query COLLATE pg_unicode_fast)) AS exact_match,
            bool_or(casefold(source.resolved_text COLLATE pg_unicode_fast)
                LIKE casefold(:prefix COLLATE pg_unicode_fast) ESCAPE '\') AS prefix_match,
            bool_or(casefold(source.resolved_text COLLATE pg_unicode_fast)
                LIKE casefold(:partial COLLATE pg_unicode_fast) ESCAPE '\') AS partial_match,
            bool_or((comparison.comparison->>'changed')::boolean) AS source_changed
        FROM ({_SOURCE_RECORDS_SQL}) AS source
        LEFT JOIN LATERAL ({_SOURCE_COMPARISON_SQL}) AS comparison
          ON CAST(:work_status AS text) = 'source_changed'
    ) AS source_projection ON true
    WHERE (CAST(:product_id AS uuid) IS NULL OR product.id = CAST(:product_id AS uuid))
      AND (CAST(:language AS text) IS NULL OR value.language = CAST(:language AS text))
    GROUP BY key.id, key.product_id, product.display_name, key.raw_key, value.language,
             scope.current_mapping_id, scope.id, mapping.base_language
    HAVING (
        NOT :has_query OR bool_or(
            (:deleted <> 'active' OR NOT value.is_deleted) AND (
            casefold(key.raw_key COLLATE pg_unicode_fast)
                LIKE casefold(:partial COLLATE pg_unicode_fast) ESCAPE '\'
            OR source_projection.partial_match
            OR casefold(value.display_text COLLATE pg_unicode_fast)
                LIKE casefold(:partial COLLATE pg_unicode_fast) ESCAPE '\'
            )
        )
    )
    AND (
        CAST(:deleted AS text) = 'all'
        OR (CAST(:deleted AS text) = 'active'
            AND NOT bool_and(key.is_deleted OR value.is_deleted))
        OR (CAST(:deleted AS text) = 'deleted'
            AND bool_and(key.is_deleted OR value.is_deleted))
    )
    AND (CAST(:state AS text) IS NULL
        OR bool_or(value.review_state = CAST(:state AS text)
            AND (:deleted <> 'active' OR NOT value.is_deleted)))
    AND (
        CAST(:violation AS text) IS NULL
        OR (CAST(:violation AS text) = 'over_limit' AND bool_or(value.is_over_limit
            AND (:deleted <> 'active' OR NOT value.is_deleted)))
        OR (CAST(:violation AS text) = 'within_limit' AND bool_or(
            value.effective_max_chars IS NOT NULL AND NOT value.is_over_limit
            AND (:deleted <> 'active' OR NOT value.is_deleted)
        ))
        OR (CAST(:violation AS text) = 'no_max'
            AND bool_or(value.effective_max_chars IS NULL
                AND (:deleted <> 'active' OR NOT value.is_deleted)))
    )
), grouped AS (
    SELECT raw_grouped.* FROM raw_grouped
    LEFT JOIN translation_proposals AS proposal
      ON proposal.translation_key_id = raw_grouped.key_id
     AND proposal.language = raw_grouped.language
    LEFT JOIN LATERAL (
        SELECT count(*) = raw_grouped.value_count
            AND bool_and(coalesce(current_value.id IS NOT NULL AND NOT current_value.is_deleted
                AND latest.revision_number = pending.basis_revision_number
                AND latest.revision_digest = pending.basis_digest, false)) AS fresh,
            bool_or(btrim(pending.proposed_text, :whitespace) = '') AS needs_translation
        FROM translation_proposal_values AS pending
        LEFT JOIN translation_values AS current_value
          ON current_value.id = pending.translation_value_id
         AND current_value.translation_key_id = raw_grouped.key_id
         AND current_value.scope_id = raw_grouped.scope_id
         AND current_value.language = raw_grouped.language
         AND current_value.selector_version = pending.selector_version
         AND current_value.selector_digest = pending.selector_digest
        LEFT JOIN LATERAL (
            SELECT revision_number, revision_digest FROM translation_value_revisions
            WHERE value_id = current_value.id ORDER BY revision_number DESC LIMIT 1
        ) AS latest ON true
        WHERE pending.proposal_id = proposal.id
    ) AS pending_work ON CAST(:work_status AS text) IS NOT NULL
    WHERE CAST(:work_status AS text) IS NULL OR (
        NOT raw_grouped.is_deleted AND raw_grouped.base_language IS NOT NULL
        AND raw_grouped.language <> raw_grouped.base_language AND (
            (CAST(:work_status AS text) = 'source_changed' AND raw_grouped.source_changed)
            OR (CAST(:work_status AS text) = 'needs_review' AND proposal.state = 'draft'
                AND NOT proposal.reconciliation_required AND pending_work.fresh)
            OR (CAST(:work_status AS text) = 'needs_translation' AND CASE
                WHEN proposal.state <> 'rejected' AND NOT proposal.reconciliation_required
                     AND pending_work.fresh THEN pending_work.needs_translation
                ELSE raw_grouped.needs_translation END)
        )
    )
), cursor_anchor AS (
    SELECT rank, stable_key, language, group_id
    FROM grouped
    WHERE group_id = :last_group_id AND rank = :last_rank
      AND language = :last_language
), page AS (
    SELECT *
    FROM grouped
    WHERE NOT :has_cursor OR (
        rank, stable_key, language COLLATE "C", group_id
    ) > (
        SELECT rank, stable_key, language COLLATE "C", group_id FROM cursor_anchor
    )
    ORDER BY rank, stable_key, language COLLATE "C", group_id
    LIMIT :lookahead
)
SELECT page.*, validity.cursor_valid, mapping.base_language AS source_language,
       locator.path AS provenance_path, locator.configured_branch AS provenance_branch,
       coalesce(repository.descriptive_name,
                repository.workspace || '/' || repository.repository_slug)
           AS provenance_repository_name,
       proposal.version AS pending_version,
       proposal.state AS pending_state,
       CASE WHEN proposal.id IS NULL THEN NULL ELSE
           proposal.reconciliation_required
           OR coalesce(pending_projection.basis_stale, false)
           OR coalesce(pending_projection.pending_value_count, 0) <> page.value_count
       END AS pending_reconciliation_required,
       pending_projection.pending_value_count,
       coalesce(discussion.comment_count, 0)::integer AS comment_count
FROM (SELECT NOT :has_cursor OR EXISTS(SELECT 1 FROM cursor_anchor) AS cursor_valid) AS validity
LEFT JOIN page ON true
LEFT JOIN product_repository_mappings AS mapping ON mapping.id = page.mapping_id
LEFT JOIN translation_value_locators AS locator ON locator.value_id = page.group_id
LEFT JOIN repositories AS repository ON repository.id = locator.repository_id
LEFT JOIN translation_proposals AS proposal
  ON proposal.translation_key_id = page.key_id
 AND proposal.language = page.language
LEFT JOIN LATERAL (
    SELECT
        count(*)::integer AS pending_value_count,
        bool_or(
            latest.revision_number IS NULL
            OR pending.basis_revision_number <> latest.revision_number
            OR pending.basis_digest <> latest.revision_digest
        ) AS basis_stale
    FROM translation_proposal_values AS pending
    LEFT JOIN LATERAL (
        SELECT revision.revision_number, revision.revision_digest
        FROM translation_value_revisions AS revision
        WHERE revision.value_id = pending.translation_value_id
        ORDER BY revision.revision_number DESC
        LIMIT 1
    ) AS latest ON true
    WHERE pending.proposal_id = proposal.id
) AS pending_projection ON proposal.id IS NOT NULL
LEFT JOIN LATERAL (
    SELECT count(*)::integer AS comment_count
    FROM translation_comments AS comment
    WHERE comment.translation_key_id = page.key_id
      AND comment.language = page.language
      AND comment.deleted_at IS NULL
) AS discussion ON page.key_id IS NOT NULL
ORDER BY page.rank, page.stable_key, page.language COLLATE "C", page.group_id
"""
)


_OPTIONS_SQL = text(
    f"""
WITH authorized_products AS (
    {_AUTHORIZED_ACTIVE_PRODUCTS_SQL}
), product_options AS (
    SELECT id, display_name, name_key COLLATE "C" AS sort_key
    FROM authorized_products
    ORDER BY sort_key, id
    LIMIT {MAX_OPTION_COUNT + 1}
), language_options AS (
    SELECT DISTINCT counts.key COLLATE "C" AS language
    FROM authorized_products AS product
    JOIN localization_scopes AS scope
      ON scope.product_id = product.id
     AND scope.active_execution_id IS NOT NULL
    CROSS JOIN LATERAL jsonb_each(scope.language_counts) AS counts
    WHERE (counts.value->>0)::bigint > 0
      AND (CAST(:product_id AS uuid) IS NULL OR product.id = CAST(:product_id AS uuid))
    ORDER BY language
    LIMIT {MAX_OPTION_COUNT + 1}
)
SELECT 0 AS option_kind, id AS product_id, display_name AS product_name,
       NULL::text AS language, sort_key
FROM product_options
UNION ALL
SELECT 1 AS option_kind, NULL::uuid AS product_id, NULL::text AS product_name,
       language, language AS sort_key
FROM language_options
ORDER BY option_kind, sort_key, product_id
"""
)


_DETAIL_SQL = text(
    f"""
WITH authorized_products AS (
    {_AUTHORIZED_ACTIVE_PRODUCTS_SQL}
), anchor AS (
    SELECT
        candidate.id AS group_id,
        key.id AS key_id,
        key.product_id,
        product.display_name AS product_name,
        key.raw_key,
        key.is_deleted AS key_deleted,
        scope.id AS scope_id,
        candidate.language,
        scope.current_mapping_id
    FROM authorized_products AS product
    JOIN localization_scopes AS scope
      ON scope.product_id = product.id
     AND scope.active_execution_id IS NOT NULL
    JOIN translation_keys AS key
      ON key.scope_id = scope.id
     AND key.product_id = product.id
    JOIN translation_values AS candidate
      ON candidate.scope_id = scope.id
     AND candidate.translation_key_id = key.id
    WHERE candidate.id = CAST(:group_id AS uuid)
      AND candidate.id = (
          SELECT member.id
          FROM translation_values AS member
          WHERE member.translation_key_id = key.id
            AND member.scope_id = scope.id
            AND member.language = candidate.language
          ORDER BY member.id
          LIMIT 1
      )
)
SELECT
    anchor.group_id,
    anchor.key_id,
    anchor.product_id,
    anchor.product_name,
    anchor.raw_key,
    anchor.key_deleted,
    anchor.language,
    value.id AS value_id,
    value.selector_version,
    value.selector_kind,
    value.selector_digest,
    value.selector_bytes,
    mapping.base_language,
    explicit_rule.max_chars AS explicit_maximum,
    explicit_rule.version AS constraint_version,
    (
        SELECT rule.max_chars
        FROM translation_constraints AS rule
        JOIN translation_keys AS base_key ON base_key.id = rule.translation_key_id
        WHERE rule.scope_id = anchor.scope_id
          AND base_key.scope_id = anchor.scope_id
          AND base_key.raw_key = anchor.raw_key
          AND rule.language = mapping.base_language
    ) AS base_maximum,
    history.entries AS history,
    value.source_text,
    value.translated_text,
    value.display_text,
    value.structure,
    value.review_state,
    value.grapheme_count,
    value.effective_max_chars,
    value.effective_constraint_source,
    value.is_over_limit,
    value.is_deleted AS value_deleted,
    value.deleted_at,
    locator.repository_id,
    coalesce(repository.descriptive_name, repository.workspace || '/' || repository.repository_slug)
        AS repository_name,
    locator.repository_side,
    locator.configured_branch,
    locator.path,
    locator.format,
    locator.source_commit_hash,
    locator.import_execution_id,
    locator.line,
    locator.column
    ,(
        SELECT count(*)::integer
        FROM translation_comments AS comment
        WHERE comment.translation_key_id = anchor.key_id
          AND comment.language = anchor.language
          AND comment.deleted_at IS NULL
    ) AS comment_count
FROM anchor
JOIN translation_values AS value
  ON value.translation_key_id = anchor.key_id
 AND value.language = anchor.language
 AND (NOT value.is_deleted OR NOT EXISTS (
     SELECT 1 FROM translation_values AS active
     WHERE active.translation_key_id=anchor.key_id AND active.scope_id=anchor.scope_id
       AND active.language=anchor.language AND NOT active.is_deleted
 ))
LEFT JOIN translation_value_locators AS locator ON locator.value_id = value.id
LEFT JOIN repositories AS repository ON repository.id = locator.repository_id
LEFT JOIN product_repository_mappings AS mapping ON mapping.id = anchor.current_mapping_id
LEFT JOIN translation_constraints AS explicit_rule
  ON explicit_rule.translation_key_id = anchor.key_id AND explicit_rule.language = anchor.language
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object(
        'revision_number', revision.revision_number, 'revision_digest', revision.revision_digest,
        'review_state', revision.review_state,
        'is_deleted', revision.is_deleted, 'created_at', revision.created_at,
        'commit_hash', revision.source_commit_hash, 'execution_id', revision.import_execution_id
    ) ORDER BY revision.revision_number DESC) AS entries
    FROM (
        SELECT * FROM translation_value_revisions
        WHERE value_id = value.id ORDER BY revision_number DESC LIMIT 51
    ) AS revision
) AS history ON true
ORDER BY locator.position NULLS LAST, value.selector_kind COLLATE "C", value.id
LIMIT {MAX_GROUP_VALUE_COUNT + 1}
"""
)


_PENDING_DETAIL_SQL = text(
    f"""
WITH authorized_products AS (
    {_AUTHORIZED_ACTIVE_PRODUCTS_SQL}
), anchor AS (
    SELECT candidate.id AS group_id, key.id AS key_id, scope.id AS scope_id,
           candidate.language
    FROM authorized_products AS product
    JOIN localization_scopes AS scope
      ON scope.product_id = product.id
     AND scope.active_execution_id IS NOT NULL
    JOIN translation_keys AS key
      ON key.scope_id = scope.id
     AND key.product_id = product.id
    JOIN translation_values AS candidate
      ON candidate.scope_id = scope.id
     AND candidate.translation_key_id = key.id
    WHERE candidate.id = CAST(:group_id AS uuid)
      AND candidate.id = (
          SELECT member.id
          FROM translation_values AS member
          WHERE member.translation_key_id = key.id
            AND member.scope_id = scope.id
            AND member.language = candidate.language
          ORDER BY member.id
          LIMIT 1
      )
)
SELECT proposal.version, proposal.state, proposal.reconciliation_required,
       proposal.updated_by, proposal.updated_at,
       pending.translation_value_id, pending.selector_version,
       pending.selector_digest, pending.basis_revision_number,
       pending.basis_digest, pending.proposed_text,
       current_value.id AS current_value_id,
       current_value.is_deleted AS current_value_deleted,
       current_value.effective_max_chars,
       latest.revision_number AS current_revision_number,
       latest.revision_digest AS current_revision_digest
FROM anchor
JOIN translation_proposals AS proposal
  ON proposal.translation_key_id = anchor.key_id
 AND proposal.language = anchor.language
LEFT JOIN translation_proposal_values AS pending ON pending.proposal_id = proposal.id
LEFT JOIN translation_values AS current_value
  ON current_value.id = pending.translation_value_id
 AND current_value.translation_key_id = anchor.key_id
 AND current_value.language = anchor.language
 AND current_value.selector_version = pending.selector_version
 AND current_value.selector_digest = pending.selector_digest
LEFT JOIN LATERAL (
    SELECT revision.revision_number, revision.revision_digest
    FROM translation_value_revisions AS revision
    WHERE revision.value_id = pending.translation_value_id
    ORDER BY revision.revision_number DESC
    LIMIT 1
) AS latest ON true
ORDER BY pending.selector_version, pending.selector_digest
LIMIT {MAX_GROUP_VALUE_COUNT + 1}
"""
)


_SOURCE_DETAIL_SQL = text(f"""
WITH source_anchor AS (
    SELECT key.id AS key_id, scope.id AS scope_id, candidate.language, mapping.base_language,
        (key.is_deleted OR NOT EXISTS (
            SELECT 1 FROM translation_values AS member
            WHERE member.translation_key_id = key.id AND member.scope_id = scope.id
                AND member.language = candidate.language AND NOT member.is_deleted
        )) AS is_deleted,
        true AS include_deleted_embedded
    FROM ({_AUTHORIZED_ACTIVE_PRODUCTS_SQL}) AS product
    JOIN localization_scopes AS scope ON scope.product_id = product.id
      AND scope.active_execution_id IS NOT NULL
    JOIN translation_keys AS key ON key.scope_id = scope.id AND key.product_id = product.id
    JOIN translation_values AS candidate ON candidate.translation_key_id = key.id
      AND candidate.scope_id = scope.id
    JOIN product_repository_mappings AS mapping ON mapping.id = scope.current_mapping_id
    WHERE candidate.id = :group_id
)
SELECT source.id AS source_value_id, source.origin, source.resolved_text AS source_text,
       source.selector_kind, source.selector_version, source.selector_bytes,
       source_anchor.base_language AS language,
       comparison.comparison AS source_comparison,
       locator.repository_id,
       coalesce(repository.descriptive_name,
                repository.workspace || '/' || repository.repository_slug)
           AS repository_name,
       locator.repository_side, locator.configured_branch, locator.path, locator.format,
       locator.source_commit_hash, locator.import_execution_id, locator.line, locator.column
FROM source_anchor
CROSS JOIN LATERAL ({_SOURCE_RECORDS_SQL}) AS source
LEFT JOIN LATERAL ({_SOURCE_COMPARISON_SQL}) AS comparison ON true
LEFT JOIN translation_value_locators AS locator ON locator.value_id = source.id
LEFT JOIN repositories AS repository ON repository.id = locator.repository_id
ORDER BY source.id LIMIT {MAX_GROUP_VALUE_COUNT + 1}
""")


_LANGUAGE_LABELS = {
    "ar": "Arabic",
    "de": "German",
    "de-DE": "German (Germany)",
    "en": "English",
    "en-GB": "English (United Kingdom)",
    "en-US": "English (United States)",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "pt-BR": "Portuguese (Brazil)",
    "zh-CN": "Chinese (China)",
}


def language_label(code: str) -> str:
    """Return a bounded server-owned label without changing the canonical code."""
    return _LANGUAGE_LABELS.get(code, code)


def _state_summary(states: tuple[StateFilter, ...]) -> StateSummary:
    """Describe a complete group's state without implying all members matched."""
    return states[0] if len(states) == 1 else "mixed"


def get_translation_options(
    session: Session, *, principal_id: UUID, product_id: UUID | None = None
) -> TranslationOptions:
    """Return current active product and language choices in server order."""
    rows = (
        session.execute(_scoped(_OPTIONS_SQL, principal_id), {"product_id": product_id})
        .mappings()
        .all()
    )
    products: list[TranslationProductOption] = []
    seen_products: set[UUID] = set()
    language_codes: set[str] = set()
    for row in rows:
        if row["option_kind"] == 1:
            language_codes.add(row["language"])
            continue
        product_id = row["product_id"]
        if product_id not in seen_products:
            products.append(TranslationProductOption(id=product_id, name=row["product_name"]))
            seen_products.add(product_id)
    if len(products) > MAX_OPTION_COUNT or len(language_codes) > MAX_OPTION_COUNT:
        raise TranslationSearchInputError("translation options exceed their allowed bound")
    languages = tuple(
        TranslationLanguageOption(code=code, label=language_label(code))
        for code in sorted(language_codes)
    )
    return TranslationOptions(products=tuple(products), languages=languages)


def _constraint_projection(row: dict[str, object]) -> TranslationConstraintProjection:
    actual = cast(int, row["grapheme_count"])
    maximum_value = row["effective_max_chars"]
    maximum = cast(int, maximum_value) if maximum_value is not None else None
    if maximum is None:
        return TranslationConstraintProjection(
            actual=actual,
            maximum=None,
            source=cast(ConstraintSource, row["effective_constraint_source"]),
            status="no_max",
            overage=None,
        )
    is_over_limit = bool(row["is_over_limit"])
    return TranslationConstraintProjection(
        actual=actual,
        maximum=maximum,
        source=cast(ConstraintSource, row["effective_constraint_source"]),
        status="over_limit" if is_over_limit else "within_limit",
        overage=actual - maximum if is_over_limit else 0,
    )


def _provenance(row: dict[str, object]) -> TranslationProvenance | None:
    if row["repository_id"] is None:
        return None
    return TranslationProvenance(
        repository_id=UUID(str(row["repository_id"])),
        repository_name=str(row["repository_name"]),
        repository_side=cast(RepositorySide, row["repository_side"]),
        branch=str(row["configured_branch"]),
        path=str(row["path"]),
        format=cast(LocalizationFormat, row["format"]),
        commit_hash=str(row["source_commit_hash"]),
        execution_id=UUID(str(row["import_execution_id"])),
        line=cast(int, row["line"]) if row["line"] is not None else None,
        column=cast(int, row["column"]) if row["column"] is not None else None,
    )


def _selector_fields(raw: object, kind: object) -> tuple[dict[str, object], ...] | None:
    """Expose typed canonical fields; malformed legacy metadata is explicitly absent."""
    try:
        payload = json.loads(bytes(cast(bytes, raw)))
        if payload["version"] != 1 or payload["kind"] != kind:
            return None
        fields = payload["fields"]
        if not isinstance(fields, dict) or len(fields) > 128:
            return None
        return tuple({"name": name, "value": value} for name, value in fields.items())
    except ValueError, TypeError, KeyError:
        return None


def _pending_detail(
    session: Session,
    *,
    group_id: UUID,
    current_value_count: int,
    group_is_deleted: bool,
) -> PendingTranslationDetail | None:
    """Project a complete pending aggregate with current server-owned eligibility."""
    raw_rows = session.execute(_PENDING_DETAIL_SQL, {"group_id": group_id}).mappings().all()
    if not raw_rows:
        return None
    if len(raw_rows) > MAX_GROUP_VALUE_COUNT:
        raise TranslationSearchInputError("translation proposal exceeds its allowed bound")
    rows = [dict(row) for row in raw_rows]
    proposal_rows = [row for row in rows if row["translation_value_id"] is not None]
    basis_stale = any(
        row["current_value_id"] is None
        or row["current_revision_number"] is None
        or row["basis_revision_number"] != row["current_revision_number"]
        or row["basis_digest"] != row["current_revision_digest"]
        for row in proposal_rows
    )
    first = rows[0]
    reconciliation_required = (
        bool(first["reconciliation_required"])
        or basis_stale
        or len(proposal_rows) != current_value_count
    )
    values: list[PendingTranslationValueDetail] = []
    for row in proposal_rows:
        text_value = str(row["proposed_text"])
        actual = grapheme_count(text_value)
        maximum = cast(int | None, row["effective_max_chars"])
        over_limit = maximum is not None and actual > maximum
        eligible = (
            not group_is_deleted
            and not reconciliation_required
            and row["current_value_id"] is not None
            and not bool(row["current_value_deleted"])
            and not over_limit
        )
        values.append(
            PendingTranslationValueDetail(
                translation_value_id=UUID(str(row["translation_value_id"])),
                selector_version=cast(Literal[1], row["selector_version"]),
                selector_digest=str(row["selector_digest"]),
                basis_revision_number=cast(int, row["basis_revision_number"]),
                basis_digest=str(row["basis_digest"]),
                text=text_value,
                grapheme_count=actual,
                maximum=maximum,
                is_over_limit=over_limit,
                approval_eligible=eligible,
                submission_eligible=eligible,
            )
        )
    return PendingTranslationDetail(
        version=cast(int, first["version"]),
        state=cast(StateFilter, first["state"]),
        reconciliation_required=reconciliation_required,
        updated_by=UUID(str(first["updated_by"])),
        updated_at=cast(datetime, first["updated_at"]),
        values=tuple(values),
    )


def _resolve_member_source(
    value: TranslationValueDetail,
    sources: tuple[dict[str, object], ...],
) -> TranslationValueDetail:
    """Match semantic selectors, never order or cross-format digests."""
    if value.is_deleted:
        # Tombstones keep their own embedded source and locator. Never reconnect
        # a removed split-format member to a source that is current today.
        return replace(
            value,
            source_value_id=value.id if value.source_text is not None else None,
            source_resolution="embedded" if value.source_text is not None else "unavailable",
            source_comparison=None,
        )
    embedded = [
        source
        for source in sources
        if source["origin"] == "embedded" and source["source_value_id"] == value.id
    ]
    compatible = [
        source
        for source in sources
        if source["origin"] == "base_language"
        and source["selector_kind"] == value.selector_kind
        and source["selector_fields"] is not None
        and _selector_identity(value.selector_kind, value.selector_fields) is not None
        and _selector_identity(source["selector_kind"], source["selector_fields"])
        == _selector_identity(value.selector_kind, value.selector_fields)
    ]
    matches = embedded or compatible
    selected = matches[0] if len(matches) == 1 else None
    resolution: SourceResolution = (
        ("embedded" if embedded else "matched")
        if selected
        else ("ambiguous" if len(matches) > 1 else "unmatched" if sources else "unavailable")
    )
    return replace(
        value,
        source_text=cast(str | None, selected["source_text"]) if selected else None,
        source_value_id=cast(UUID, selected["source_value_id"]) if selected else None,
        source_resolution=resolution,
        source_comparison=cast(dict[str, object] | None, selected["source_comparison"])
        if selected
        else None,
    )


def _selector_identity(kind: object, fields: object) -> object:
    """Only parser-owned semantic selectors identify a split-format counterpart."""
    if not isinstance(fields, (tuple, list)):
        return None
    values = {field["name"]: field["value"] for field in fields}
    field_name = {
        "android_quantity": "quantity",
        "android_array_item": "index",
        "json_path": "parents",
    }.get(str(kind))
    if kind == "scalar":
        return ("scalar",) if not values else None
    if field_name is not None and field_name in values:
        return (kind, values[field_name])
    return None


def get_translation_group(
    session: Session,
    *,
    group_id: UUID,
) -> TranslationGroupDetail:
    """Resolve only a server-issued group UUID from one active-dataset statement."""
    raw_rows = session.execute(_DETAIL_SQL, {"group_id": group_id}).mappings().all()
    if not raw_rows:
        raise TranslationGroupUnavailable("translation unavailable")
    if len(raw_rows) > MAX_GROUP_VALUE_COUNT:
        raise TranslationSearchInputError("translation group exceeds its allowed bound")
    rows = [dict(row) for row in raw_rows]
    states = cast(
        tuple[StateFilter, ...],
        tuple(sorted({str(row["review_state"]) for row in rows})),
    )
    values = tuple(
        TranslationValueDetail(
            id=UUID(str(row["value_id"])),
            selector_version=cast(Literal[1], row["selector_version"]),
            selector_kind=cast(SelectorKind, row["selector_kind"]),
            selector_digest=str(row["selector_digest"]),
            selector_fields=_selector_fields(row["selector_bytes"], row["selector_kind"]),
            history=tuple(cast(list[dict[str, object]], row["history"] or [])[:50]),
            history_has_more=len(cast(list[object], row["history"] or [])) > 50,
            source_text=(str(row["source_text"]) if row["source_text"] is not None else None),
            translated_text=(
                str(row["translated_text"]) if row["translated_text"] is not None else None
            ),
            display_text=str(row["display_text"]),
            structure=tuple(row["structure"]),
            review_state=cast(StateFilter, row["review_state"]),
            grapheme_count=cast(int, row["grapheme_count"]),
            constraint=_constraint_projection(row),
            is_deleted=bool(row["value_deleted"]),
            deleted_at=row["deleted_at"],
            provenance=_provenance(row),
        )
        for row in rows
    )
    source_rows = session.execute(_SOURCE_DETAIL_SQL, {"group_id": group_id}).mappings().all()
    if len(source_rows) > MAX_GROUP_VALUE_COUNT:
        raise TranslationSearchInputError("translation source context exceeds its allowed bound")
    source_context = tuple(
        {
            "source_value_id": row["source_value_id"],
            "origin": row["origin"],
            "language": row["language"],
            "selector_kind": row["selector_kind"],
            "selector_fields": _selector_fields(row["selector_bytes"], row["selector_kind"]),
            "source_text": row["source_text"],
            "source_comparison": row["source_comparison"],
            "provenance": asdict(provenance) if (provenance := _provenance(dict(row))) else None,
        }
        for row in source_rows
    )
    values = tuple(_resolve_member_source(value, source_context) for value in values)
    first = rows[0]
    group_is_deleted = bool(first["key_deleted"]) or all(value.is_deleted for value in values)
    pending_change = _pending_detail(
        session,
        group_id=group_id,
        current_value_count=len(values),
        group_is_deleted=group_is_deleted,
    )
    mutation_eligible = not group_is_deleted
    review_eligible = bool(
        pending_change is not None
        and not pending_change.reconciliation_required
        and len(pending_change.values) == len(values)
        and all(value.approval_eligible for value in pending_change.values)
    )
    return TranslationGroupDetail(
        id=UUID(str(first["group_id"])),
        product_id=UUID(str(first["product_id"])),
        product_name=str(first["product_name"]),
        raw_key=str(first["raw_key"]),
        language=str(first["language"]),
        states=states,
        state_summary=_state_summary(states),
        is_deleted=group_is_deleted,
        values=values,
        base_language=cast(str | None, first["base_language"]),
        explicit_maximum=cast(int | None, first["explicit_maximum"]),
        constraint_version=cast(int | None, first["constraint_version"]),
        base_maximum=cast(int | None, first["base_maximum"]),
        pending_change=pending_change,
        comment_count=cast(int, first["comment_count"]),
        mutation_eligible=mutation_eligible,
        review_eligible=review_eligible,
        source_context=source_context,
    )


def search_translations(
    session: Session,
    *,
    principal_id: UUID,
    filters: TranslationSearchFilters,
    cursor: str | None,
    cursor_secret: str,
) -> TranslationSearchPage:
    """Return one stable page from active products and exact active datasets."""
    if not cursor_secret:
        raise TranslationSearchInputError("cursor signing secret is required")
    scope_digest = _scope_digest(session, principal_id=principal_id, filters=filters)
    position = (
        _decode_cursor(
            cursor,
            scope_digest=scope_digest,
            filters=filters,
            cursor_secret=cursor_secret,
        )
        if cursor is not None
        else None
    )
    escaped_query = escape_like_literal(filters.query or "")
    rows = (
        session.execute(
            _scoped(_SEARCH_SQL, principal_id),
            {
                "deleted": filters.deleted,
                "has_cursor": position is not None,
                "has_query": filters.query is not None,
                "language": filters.language,
                "last_group_id": position.group_id if position is not None else _ZERO_UUID,
                "last_language": position.language if position is not None else "",
                "last_rank": position.rank if position is not None else -1,
                "lookahead": filters.page_size + 1,
                "partial": f"%{escaped_query}%",
                "prefix": f"{escaped_query}%",
                "product_id": filters.product_id,
                "query": filters.query or "",
                "state": filters.state,
                "violation": filters.violation,
                "work_status": filters.work_status,
                "whitespace": _WHITESPACE,
            },
        )
        .mappings()
        .all()
    )
    if not rows[0]["cursor_valid"]:
        raise InvalidTranslationCursor("invalid translation cursor")
    rows = [row for row in rows if row["group_id"] is not None]
    has_more = len(rows) > filters.page_size
    visible_rows = rows[: filters.page_size]
    items = tuple(
        TranslationGroupSummary(
            id=row["group_id"],
            product_id=row["product_id"],
            product_name=row["product_name"],
            raw_key=row["raw_key"],
            language=row["language"],
            rank=row["rank"],
            source_text=row["source_text"],
            source_language=row["source_language"],
            translated_text=row["translated_text"],
            selector_kinds=tuple(row["selector_kinds"]),
            provenance=(
                TranslationSummaryProvenance(
                    repository_name=row["provenance_repository_name"],
                    branch=row["provenance_branch"],
                    path=row["provenance_path"],
                )
                if row["provenance_path"] is not None
                else None
            ),
            value_count=row["value_count"],
            over_limit_count=row["over_limit_count"],
            within_limit_count=row["within_limit_count"],
            no_max_count=row["no_max_count"],
            states=cast(tuple[StateFilter, ...], tuple(row["states"])),
            state_summary=_state_summary(cast(tuple[StateFilter, ...], tuple(row["states"]))),
            has_over_limit=row["has_over_limit"],
            has_no_max=row["has_no_max"],
            is_deleted=row["is_deleted"],
            pending_change=(
                PendingTranslationSummary(
                    version=row["pending_version"],
                    state=cast(StateFilter, row["pending_state"]),
                    reconciliation_required=row["pending_reconciliation_required"],
                    value_count=row["pending_value_count"],
                )
                if row["pending_version"] is not None
                else None
            ),
            comment_count=row["comment_count"],
        )
        for row in visible_rows
    )
    next_cursor = None
    if has_more and visible_rows:
        last = visible_rows[-1]
        next_cursor = _encode_cursor(
            scope_digest=scope_digest,
            filters=filters,
            position=_CursorPosition(
                rank=last["rank"],
                language=last["language"],
                group_id=last["group_id"],
            ),
            cursor_secret=cursor_secret,
        )
    return TranslationSearchPage(items=items, next_cursor=next_cursor)
