"""Versioned current terminology, with bounded per-project language-pair lookup."""

import hashlib
import json
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from verboflex.audit.ledger import record_audit
from verboflex.models.glossary import GlossaryEntry
from verboflex.schemas.glossary import (
    GlossaryInput,
    GlossaryMatches,
    GlossaryMatchQuery,
    GlossaryPage,
    GlossaryResponse,
)
from verboflex.services.translation_authoring import AuthoringError, _product


def response(row: GlossaryEntry) -> GlossaryResponse:
    return GlossaryResponse(
        id=row.id,
        version=row.version,
        expected_version=row.version,
        source_language=row.source_language,
        target_language=row.target_language,
        source_term=row.source_term,
        target_term=row.target_term,
        forbidden=row.forbidden,
        case_sensitive=row.case_sensitive,
        note=row.note,
        updated_at=row.updated_at,
    )


def list_entries(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    after: UUID | None = None,
    query: str = "",
) -> GlossaryPage:
    _product(session, product_id, actor_id, "read")
    stmt = select(GlossaryEntry).where(GlossaryEntry.product_id == product_id)
    if after is not None:
        stmt = stmt.where(GlossaryEntry.id > after)
    if query:
        stmt = stmt.where(
            GlossaryEntry.source_term.icontains(query, autoescape=True)
            | GlossaryEntry.target_term.icontains(query, autoescape=True)
        )
    rows = session.scalars(stmt.order_by(GlossaryEntry.id).limit(51)).all()
    return GlossaryPage(
        items=[response(row) for row in rows[:50]],
        next_after=rows[49].id if len(rows) > 50 else None,
    )


def save(
    session: Session, *, product_id: UUID, actor_id: UUID, entry_id: UUID, data: GlossaryInput
) -> GlossaryResponse:
    _product(session, product_id, actor_id, "review")
    data = data.model_copy(
        update={"source_term": data.source_term.strip(), "target_term": data.target_term.strip()}
    )
    identity = hashlib.sha256(
        json.dumps(
            [
                data.source_language,
                data.target_language,
                data.source_term.casefold(),
                data.target_term.casefold(),
            ],
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    fields = data.model_dump(exclude={"expected_version"})
    row = session.get(GlossaryEntry, entry_id, with_for_update=True)
    if row is not None:
        if row.product_id != product_id:
            raise AuthoringError("Glossary entry unavailable", 404)
        if row.version != data.expected_version:
            if (
                row.version == data.expected_version + 1
                and row.updated_by == actor_id
                and all(getattr(row, k) == v for k, v in fields.items())
            ):
                return response(row)
            raise AuthoringError("This term changed. Reload before saving", 409)
    elif data.expected_version != 0:
        raise AuthoringError("Glossary entry no longer exists", 409)
    duplicate = session.scalar(
        select(GlossaryEntry.id).where(
            GlossaryEntry.product_id == product_id,
            GlossaryEntry.identity_digest == identity,
            GlossaryEntry.id != entry_id,
        )
    )
    if duplicate:
        raise AuthoringError("This term already exists", 409)
    if row is None:
        count = session.scalar(
            select(func.count())
            .select_from(GlossaryEntry)
            .where(GlossaryEntry.product_id == product_id)
        )
        if count is not None and count >= 5000:
            raise AuthoringError("This project has reached its 5,000-term limit", 422)
        row = GlossaryEntry(
            id=entry_id,
            product_id=product_id,
            created_by=actor_id,
            updated_by=actor_id,
            identity_digest=identity,
            version=1,
            **fields,
        )
        session.add(row)
    else:
        row.version += 1
        row.identity_digest = identity
        row.updated_by = actor_id
        for key, value in fields.items():
            setattr(row, key, value)
    row.updated_at = datetime.now(UTC)
    record_audit(session, actor_id=actor_id, action="glossary.saved", entity_id=row.id)
    session.flush()
    return response(row)


def delete(
    session: Session, *, product_id: UUID, actor_id: UUID, entry_id: UUID, expected_version: int
) -> None:
    _product(session, product_id, actor_id, "review")
    row = session.get(GlossaryEntry, entry_id, with_for_update=True)
    if row is None or row.product_id != product_id:
        raise AuthoringError("Glossary entry unavailable", 404)
    if row.version != expected_version:
        raise AuthoringError("This term changed. Reload before deleting", 409)
    record_audit(session, actor_id=actor_id, action="glossary.deleted", entity_id=row.id)
    session.delete(row)
    session.flush()


def contains_term(text: str, term: str, *, case_sensitive: bool) -> bool:
    if not case_sensitive:
        text, term = text.casefold(), term.casefold()
    # Avoid matching “app” inside “happy”; scripts without word separators retain
    # substring matching for terminology embedded in a sentence.
    word_boundaries = all(ord(c) < 0x2E80 for c in term)
    before = r"(?<!\w)" if word_boundaries and term[0].isalnum() else ""
    after = r"(?!\w)" if word_boundaries and term[-1].isalnum() else ""
    return re.search(before + re.escape(term) + after, text) is not None


def matches(
    session: Session, *, product_id: UUID, actor_id: UUID, query: GlossaryMatchQuery
) -> GlossaryMatches:
    _product(session, product_id, actor_id, "read")
    # At most 5,000 terms per project; this index bounds even multi-million-string
    # products independently of their translation corpus. Read only short terms.
    rows = session.scalars(
        select(GlossaryEntry)
        .where(
            GlossaryEntry.product_id == product_id,
            GlossaryEntry.source_language == query.source_language,
            GlossaryEntry.target_language == query.target_language,
        )
        .order_by(GlossaryEntry.id)
        .limit(5001)
    ).all()
    found = [
        row
        for row in rows
        if contains_term(query.source_text, row.source_term, case_sensitive=row.case_sensitive)
    ]
    return GlossaryMatches(items=[response(row) for row in found[:50]], truncated=len(found) > 50)
