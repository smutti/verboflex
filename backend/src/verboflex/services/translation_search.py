"""Bounded, authorization-safe search over exact active localization datasets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

SEARCH_PAGE_SIZE = 50
MAX_SEARCH_QUERY_CHARS = 256
MAX_CURSOR_CHARS = 2048
CURSOR_VERSION = 1
_ZERO_UUID = UUID(int=0)

DeletedMode = Literal["active", "deleted", "all"]
StateFilter = Literal["draft", "approved", "rejected"]
ViolationFilter = Literal["over_limit", "within_limit", "no_max"]


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
class TranslationGroupSummary:
    """One raw-key plus language group without selector loss."""

    id: UUID
    product_id: UUID
    product_name: str
    raw_key: str
    language: str
    rank: int
    source_text: str | None
    translated_text: str | None
    value_count: int
    states: tuple[str, ...]
    state_summary: str
    has_over_limit: bool
    has_no_max: bool
    is_deleted: bool


@dataclass(frozen=True, slots=True)
class TranslationSearchPage:
    """One exact 50-group keyset page."""

    items: tuple[TranslationGroupSummary, ...]
    next_cursor: str | None


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
            "FROM products AS product "
            "JOIN localization_scopes AS scope ON scope.product_id = product.id "
            "WHERE product.is_active "
            "AND scope.active_execution_id IS NOT NULL "
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
    r"""
WITH grouped AS (
    SELECT
        (array_agg(value.id ORDER BY value.id))[1] AS group_id,
        key.id AS key_id,
        key.product_id,
        product.display_name AS product_name,
        key.raw_key,
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
        array_agg(DISTINCT value.review_state ORDER BY value.review_state) AS states,
        bool_or(value.is_over_limit) AS has_over_limit,
        bool_or(value.effective_max_chars IS NULL) AS has_no_max,
        bool_or(key.is_deleted OR value.is_deleted) AS is_deleted
    FROM products AS product
    JOIN localization_scopes AS scope
      ON scope.product_id = product.id
     AND scope.active_execution_id IS NOT NULL
    JOIN translation_keys AS key
      ON key.scope_id = scope.id
     AND key.product_id = product.id
    JOIN translation_values AS value
      ON value.scope_id = scope.id
     AND value.translation_key_id = key.id
    WHERE product.is_active
      AND (CAST(:product_id AS uuid) IS NULL OR product.id = CAST(:product_id AS uuid))
      AND (CAST(:language AS text) IS NULL OR value.language = CAST(:language AS text))
    GROUP BY key.id, key.product_id, product.display_name, key.raw_key, value.language
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
SELECT * FROM page
ORDER BY rank, stable_key, language COLLATE "C", group_id
"""
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
            translated_text=row["translated_text"],
            value_count=row["value_count"],
            states=tuple(row["states"]),
            state_summary=(row["states"][0] if len(row["states"]) == 1 else "mixed"),
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
