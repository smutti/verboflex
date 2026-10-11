"""Bounded suggestions over live indexed content, without a historical copy."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from verboflex.localization.placeholders import compatible_arguments
from verboflex.schemas.reuse import ReusePage, ReuseQuery, ReuseResolve, ReuseSuggestion
from verboflex.services.translation_authoring import AuthoringError, _product

# Exact SHA index is installed in 0040. Fuzzy uses the existing source_text GIN
# expression. Every lookup remains tied to a published, active project/scope.
_SOURCE_HASH = "sha256(replace(source.source_text, chr(92), chr(92)||chr(92))::bytea)"
_NORMALIZED = "casefold((coalesce(source.source_text, '') COLLATE pg_unicode_fast))"
_BASE_SQL = """
SELECT source.id AS source_value_id, target.id AS target_value_id,
       product.id AS product_id, product.display_name AS product_name,
       left(key.raw_key, 4096) AS raw_key, source.source_text,
       coalesce(approved.proposed_text, target.display_text) AS target_text,
       approved.version AS proposal_version, approved.id AS proposal_id,
       repository.workspace || '/' || repository.repository_slug AS repository,
       locator.path AS file,
       (SELECT member.id FROM translation_values member
        WHERE member.translation_key_id=key.id AND member.language=target.language
          AND NOT member.is_deleted ORDER BY member.id LIMIT 1) AS group_id,
       {score} AS score
FROM translation_values source
JOIN localization_scopes scope ON scope.id=source.scope_id
JOIN products product ON product.id=scope.product_id
  AND product.active_revision_id=scope.current_revision_id
JOIN product_repository_mappings mapping ON mapping.id=scope.current_mapping_id
JOIN translation_keys key ON key.id=source.translation_key_id AND key.scope_id=scope.id
JOIN translation_values target ON target.translation_key_id=key.id AND target.scope_id=scope.id
  AND target.language=:target_language
  AND ((source.id=target.id AND source.language=:target_language)
    OR (source.language=:source_language AND target.source_text IS NULL
      AND source.selector_digest=target.selector_digest))
JOIN translation_value_locators locator ON locator.value_id=target.id
  AND locator.import_execution_id=scope.active_execution_id
JOIN repositories repository ON repository.id=locator.repository_id
LEFT JOIN LATERAL (
    SELECT proposal.id, proposal.version, pending.proposed_text
    FROM translation_proposals proposal
    JOIN translation_proposal_values pending ON pending.proposal_id=proposal.id
      AND pending.translation_value_id=target.id
      AND pending.selector_digest=target.selector_digest
    JOIN LATERAL (
        SELECT revision_number, revision_digest FROM translation_value_revisions
        WHERE value_id=target.id ORDER BY revision_number DESC LIMIT 1
    ) latest ON latest.revision_number=pending.basis_revision_number
        AND latest.revision_digest=pending.basis_digest
    WHERE proposal.translation_key_id=key.id AND proposal.language=target.language
      AND proposal.state='approved' AND NOT proposal.reconciliation_required
      AND proposal.updated_at >= (SELECT created_at FROM translation_value_revisions
          WHERE value_id=source.id ORDER BY revision_number DESC LIMIT 1)
    LIMIT 1
) approved ON true
WHERE product.id=:product_id AND product.is_active AND product.deleted_at IS NULL
  AND scope.active_execution_id IS NOT NULL AND NOT key.is_deleted
  AND NOT source.is_deleted AND NOT target.is_deleted
  AND source.source_text IS NOT NULL AND char_length(source.source_text) BETWEEN 1 AND 4096
  AND mapping.base_language=:source_language
  AND locator.format=:format AND target.selector_kind=:selector_kind
  AND (CAST(:exclude_value_id AS uuid) IS NULL OR target.id != CAST(:exclude_value_id AS uuid))
  AND (CAST(:selector_form AS text) IS NULL OR
       convert_from(target.selector_bytes,'UTF8')::jsonb->'fields'->>
       CASE WHEN target.selector_kind='android_quantity' THEN 'quantity' ELSE 'form_index' END
       = :selector_form)
  AND char_length(coalesce(approved.proposed_text, target.display_text)) BETWEEN 1 AND 4096
  AND {predicate}
ORDER BY score DESC, (approved.id IS NOT NULL) DESC, target.id
LIMIT 50
"""


def _rows(
    session: Session,
    product_id: UUID,
    query: ReuseQuery,
    *,
    fuzzy: bool = False,
    selected: ReuseResolve | None = None,
) -> list[ReuseSuggestion]:
    if selected is not None:
        predicate = "source.id=:source_value_id AND target.id=:target_value_id"
    elif fuzzy:
        predicate = f"{_NORMALIZED} % :normalized AND source.source_text <> :source_text"
    else:
        predicate = f"{_SOURCE_HASH}=:source_digest AND source.source_text=:source_text"
    score = f"similarity({_NORMALIZED}, :normalized)" if fuzzy or selected else "1.0"
    parameters = {
        "product_id": product_id,
        "source_text": query.source_text,
        "source_digest": hashlib.sha256(query.source_text.encode()).digest(),
        "normalized": query.source_text.casefold(),
        "source_language": query.source_language,
        "target_language": query.target_language,
        "format": query.format,
        "selector_kind": query.selector_kind,
        "selector_form": query.selector_form,
        "exclude_value_id": query.exclude_value_id,
        "source_value_id": selected.source_value_id if selected else None,
        "target_value_id": selected.target_value_id if selected else None,
    }
    result = []
    for row in session.execute(
        text(_BASE_SQL.format(score=score, predicate=predicate)), parameters
    ).mappings():
        source, target = row["source_text"], row["target_text"]
        if not target.strip() or not compatible_arguments(query.source_text, target, query.format):
            continue
        if not compatible_arguments(query.source_text, source, query.format):
            continue
        exact = source == query.source_text
        if not exact and (not query.fuzzy or len(query.source_text) < 5 or row["score"] < 0.45):
            continue
        digest = hashlib.sha256(
            json.dumps(
                [
                    str(row["source_value_id"]),
                    str(row["target_value_id"]),
                    source,
                    target,
                    row["proposal_version"],
                    str(row["proposal_id"]),
                    row["file"],
                    query.source_language,
                    query.target_language,
                    query.format,
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        result.append(
            ReuseSuggestion(
                source_value_id=row["source_value_id"],
                target_value_id=row["target_value_id"],
                group_id=row["group_id"],
                product_id=row["product_id"],
                product_name=row["product_name"],
                key=row["raw_key"],
                source_text=source,
                target_text=target,
                source_language=query.source_language,
                target_language=query.target_language,
                match_percent=100 if exact else min(99, round(row["score"] * 100)),
                origin="approved_draft" if row["proposal_id"] else "repository",
                proposal_version=row["proposal_version"],
                repository=row["repository"],
                file=row["file"],
                digest=digest,
            )
        )
    return result


def suggest(session: Session, *, product_id: UUID, actor_id: UUID, query: ReuseQuery) -> ReusePage:
    _product(session, product_id, actor_id, "read")
    session.execute(text("SET LOCAL statement_timeout = '1500ms'"))
    try:
        candidates = _rows(session, product_id, query)
        if query.fuzzy and len(query.source_text) >= 5:
            candidates += _rows(session, product_id, query, fuzzy=True)
    except DBAPIError:
        raise AuthoringError("Suggestions are temporarily unavailable", 503) from None
    seen = set()
    result = []
    for candidate in candidates:
        identity = (candidate.source_text, candidate.target_text)
        if identity not in seen:
            seen.add(identity)
            result.append(candidate)
        if len(result) == 20:
            break
    return ReusePage(items=result)


def resolve(
    session: Session, *, product_id: UUID, actor_id: UUID, data: ReuseResolve
) -> ReuseSuggestion:
    _product(session, product_id, actor_id, "read")
    session.execute(text("SET LOCAL statement_timeout = '1500ms'"))
    try:
        candidates = _rows(session, product_id, data.query, selected=data)
    except DBAPIError:
        raise AuthoringError("Suggestion is temporarily unavailable", 503) from None
    if len(candidates) != 1 or candidates[0].digest != data.expected_digest:
        raise AuthoringError("This suggestion changed. Refresh suggestions", 409)
    return candidates[0]
