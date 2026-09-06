"""Bounded, authorization-safe search over exact active localization datasets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

SEARCH_PAGE_SIZE = 50
MAX_SEARCH_QUERY_CHARS = 256
MAX_CURSOR_CHARS = 2048
CURSOR_VERSION = 1
MAX_OPTION_COUNT = 500
MAX_GROUP_VALUE_COUNT = 10_000
_ZERO_UUID = UUID(int=0)
_AUTHORIZED_ACTIVE_PRODUCTS_SQL = "SELECT id, display_name, name_key FROM products WHERE is_active"

DeletedMode = Literal["active", "deleted", "all"]
StateFilter = Literal["draft", "approved", "rejected"]
ViolationFilter = Literal["over_limit", "within_limit", "no_max"]
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
LocalizationFormat = Literal["android_xml", "qt_ts", "json", "ios_strings"]


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
    pending_change: None = None
    comments: tuple[str, ...] = ()


class TranslationGroupUnavailable(LookupError):
    """Bounded missing-or-inaccessible group result."""


@dataclass(frozen=True, slots=True)
class _CursorPosition:
    rank: int
    stable_key: str
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


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _canonical_filter(filters: TranslationSearchFilters) -> dict[str, object]:
    return {
        "deleted": filters.deleted,
        "language": filters.language,
        "page_size": filters.page_size,
        "product_id": str(filters.product_id) if filters.product_id is not None else None,
        "query": filters.query,
        "state": filters.state,
        "violation": filters.violation,
    }


def _scope_digest(
    session: Session,
    *,
    principal_id: UUID,
) -> str:
    rows = session.execute(
        text(
            "SELECT product.id AS product_id, scope.id AS scope_id, "
            "scope.active_execution_id, scope.dataset_version "
            f"FROM ({_AUTHORIZED_ACTIVE_PRODUCTS_SQL}) AS product "
            "JOIN localization_scopes AS scope ON scope.product_id = product.id "
            "WHERE scope.active_execution_id IS NOT NULL "
            "ORDER BY product.id, scope.id "
            "FOR SHARE OF product, scope"
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
        "filters": _canonical_filter(filters),
        "last": [
            position.rank,
            position.stable_key,
            position.language,
            str(position.group_id),
        ],
        "scope": scope_digest,
        "v": CURSOR_VERSION,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.digest(cursor_secret.encode(), body, "sha256")
    cursor = f"{_b64encode(body)}.{_b64encode(signature)}"
    if len(cursor) > MAX_CURSOR_CHARS:
        raise TranslationSearchInputError("cursor exceeds its allowed bound")
    return cursor


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
        encoded_body, encoded_signature = cursor.split(".", 1)
        body = _b64decode(encoded_body)
        signature = _b64decode(encoded_signature)
        if _b64encode(body) != encoded_body or _b64encode(signature) != encoded_signature:
            raise ValueError
        expected_signature = hmac.digest(cursor_secret.encode(), body, "sha256")
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError
        payload = json.loads(body)
        if set(payload) != {"filters", "last", "scope", "v"}:
            raise ValueError
        if payload["v"] != CURSOR_VERSION:
            raise ValueError
        if payload["scope"] != scope_digest:
            raise ValueError
        if payload["filters"] != _canonical_filter(filters):
            raise ValueError
        last = payload["last"]
        if not isinstance(last, list) or len(last) != 4:
            raise ValueError
        position = _CursorPosition(
            rank=int(last[0]),
            stable_key=str(last[1]),
            language=str(last[2]),
            group_id=UUID(str(last[3])),
        )
        if position.rank not in (0, 1, 2, 3):
            raise ValueError
        return position
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidTranslationCursor("invalid translation cursor") from error


_SEARCH_SQL = text(
    rf"""
WITH authorized_products AS (
    {_AUTHORIZED_ACTIVE_PRODUCTS_SQL}
), grouped AS (
    SELECT
        (array_agg(value.id ORDER BY value.id))[1] AS group_id,
        key.id AS key_id,
        key.product_id,
        product.display_name AS product_name,
        key.raw_key,
        scope.current_mapping_id AS mapping_id,
        replace(lower(key.raw_key), 'ß', 'ss') COLLATE "C" AS stable_key,
        value.language,
        CASE
            WHEN NOT :has_query THEN 3
            WHEN bool_or(
                replace(lower(key.raw_key), 'ß', 'ss') = :query
                OR replace(lower(coalesce(value.source_text, '')), 'ß', 'ss') = :query
                OR replace(lower(value.display_text), 'ß', 'ss') = :query
            ) THEN 0
            WHEN bool_or(
                replace(lower(key.raw_key), 'ß', 'ss') LIKE :prefix ESCAPE '\'
                OR replace(lower(coalesce(value.source_text, '')), 'ß', 'ss')
                    LIKE :prefix ESCAPE '\'
                OR replace(lower(value.display_text), 'ß', 'ss') LIKE :prefix ESCAPE '\'
            ) THEN 1
            ELSE 2
        END AS rank,
        (array_agg(value.source_text ORDER BY value.id)
            FILTER (WHERE value.source_text IS NOT NULL))[1] AS source_text,
        (array_agg(value.translated_text ORDER BY value.id)
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
        bool_or(key.is_deleted OR value.is_deleted) AS is_deleted
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
    WHERE (CAST(:product_id AS uuid) IS NULL OR product.id = CAST(:product_id AS uuid))
      AND (CAST(:language AS text) IS NULL OR value.language = CAST(:language AS text))
    GROUP BY key.id, key.product_id, product.display_name, key.raw_key, value.language,
             scope.current_mapping_id
    HAVING (
        NOT :has_query OR bool_or(
            replace(lower(key.raw_key), 'ß', 'ss') LIKE :partial ESCAPE '\'
            OR replace(lower(coalesce(value.source_text, '')), 'ß', 'ss')
                LIKE :partial ESCAPE '\'
            OR replace(lower(value.display_text), 'ß', 'ss') LIKE :partial ESCAPE '\'
        )
    )
    AND (
        CAST(:deleted AS text) = 'all'
        OR (CAST(:deleted AS text) = 'active'
            AND NOT bool_or(key.is_deleted OR value.is_deleted))
        OR (CAST(:deleted AS text) = 'deleted'
            AND bool_or(key.is_deleted OR value.is_deleted))
    )
    AND (CAST(:state AS text) IS NULL
        OR bool_or(value.review_state = CAST(:state AS text)))
    AND (
        CAST(:violation AS text) IS NULL
        OR (CAST(:violation AS text) = 'over_limit' AND bool_or(value.is_over_limit))
        OR (CAST(:violation AS text) = 'within_limit' AND bool_or(
            value.effective_max_chars IS NOT NULL AND NOT value.is_over_limit
        ))
        OR (CAST(:violation AS text) = 'no_max'
            AND bool_or(value.effective_max_chars IS NULL))
    )
), page AS (
    SELECT *
    FROM grouped
    WHERE NOT :has_cursor OR (
        rank, stable_key, language COLLATE "C", group_id
    ) > (
        :last_rank, :last_key COLLATE "C", :last_language COLLATE "C", :last_group_id
    )
    ORDER BY rank, stable_key, language COLLATE "C", group_id
    LIMIT :lookahead
)
SELECT page.*, mapping.base_language AS source_language,
       locator.path AS provenance_path, locator.configured_branch AS provenance_branch,
       coalesce(repository.descriptive_name,
                repository.workspace || '/' || repository.repository_slug)
           AS provenance_repository_name
FROM page
JOIN product_repository_mappings AS mapping ON mapping.id = page.mapping_id
LEFT JOIN translation_value_locators AS locator ON locator.value_id = page.group_id
LEFT JOIN repositories AS repository ON repository.id = locator.repository_id
ORDER BY rank, stable_key, language COLLATE "C", group_id
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
    SELECT DISTINCT value.language COLLATE "C" AS language
    FROM authorized_products AS product
    JOIN localization_scopes AS scope
      ON scope.product_id = product.id
     AND scope.active_execution_id IS NOT NULL
    JOIN translation_values AS value ON value.scope_id = scope.id
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
SELECT
    anchor.group_id,
    anchor.product_id,
    anchor.product_name,
    anchor.raw_key,
    anchor.key_deleted,
    anchor.language,
    value.id AS value_id,
    value.selector_version,
    value.selector_kind,
    value.selector_digest,
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
FROM anchor
JOIN translation_values AS value
  ON value.translation_key_id = anchor.key_id
 AND value.language = anchor.language
LEFT JOIN translation_value_locators AS locator ON locator.value_id = value.id
LEFT JOIN repositories AS repository ON repository.id = locator.repository_id
ORDER BY locator.position NULLS LAST, value.selector_kind COLLATE "C", value.id
LIMIT {MAX_GROUP_VALUE_COUNT + 1}
"""
)


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


def get_translation_options(session: Session) -> TranslationOptions:
    """Return current active product and language choices in server order."""
    rows = session.execute(_OPTIONS_SQL).mappings().all()
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
    first = rows[0]
    return TranslationGroupDetail(
        id=UUID(str(first["group_id"])),
        product_id=UUID(str(first["product_id"])),
        product_name=str(first["product_name"]),
        raw_key=str(first["raw_key"]),
        language=str(first["language"]),
        states=states,
        state_summary=_state_summary(states),
        is_deleted=bool(first["key_deleted"]) or any(value.is_deleted for value in values),
        values=values,
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
    scope_digest = _scope_digest(session, principal_id=principal_id)
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
            _SEARCH_SQL,
            {
                "deleted": filters.deleted,
                "has_cursor": position is not None,
                "has_query": filters.query is not None,
                "language": filters.language,
                "last_group_id": position.group_id if position is not None else _ZERO_UUID,
                "last_key": position.stable_key if position is not None else "",
                "last_language": position.language if position is not None else "",
                "last_rank": position.rank if position is not None else -1,
                "lookahead": filters.page_size + 1,
                "partial": f"%{escaped_query}%",
                "prefix": f"{escaped_query}%",
                "product_id": filters.product_id,
                "query": filters.query or "",
                "state": filters.state,
                "violation": filters.violation,
            },
        )
        .mappings()
        .all()
    )
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
                stable_key=last["stable_key"],
                language=last["language"],
                group_id=last["group_id"],
            ),
            cursor_secret=cursor_secret,
        )
    return TranslationSearchPage(items=items, next_cursor=next_cursor)
