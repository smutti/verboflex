"""Bounded PostgreSQL projections over immutable submission children, never proof blobs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select, text, tuple_
from sqlalchemy.orm import Session

from verboflex.integrations.bitbucket.urls import validate_pull_request_url
from verboflex.models.submission import (
    ChangeSet,
    ChangeSetEvent,
    ChangeSetFile,
    ChangeSetItem,
    SubmissionBatch,
)
from verboflex.models.user import User
from verboflex.schemas.submissions import (
    AuthorityReceiptResponse,
    BranchReceiptResponse,
    ChangeSetActivityPage,
    ChangeSetActivityResponse,
    ChangeSetFileResponse,
    ChangeSetFilesPage,
    ChangeSetHistoryPage,
    ChangeSetItemResponse,
    ChangeSetItemsPage,
    ChangeSetSource,
    ChangeSetValueResponse,
    ChangeSetValuesPage,
    CommitReceiptResponse,
    PullRequestReceiptResponse,
    SubmissionActor,
)
from verboflex.services.signed_cursor import InvalidSignedCursor, SignedCursorCodec
from verboflex.services.submission_reviews import SubmissionReviewUnavailable, _product_actor
from verboflex.services.submissions import SubmissionConflict, change_set_response

PAGE_SIZE = 25
MAX_PAGE_BYTES = 4 * 1024 * 1024
_CURSOR_KEYS = frozenset({"scope", "actor", "stamp", "key", "size", "last", "version"})


class InvalidSubmissionCursor(ValueError):
    pass


def _binding(
    product_id: UUID, actor: User, kind: str, group_id: UUID | None, key_id: UUID | None
) -> dict[str, object]:
    return {
        "scope": [str(product_id), str(group_id) if group_id else None, kind],
        "actor": str(actor.id),
        "stamp": actor.token_version,
        "key": str(key_id) if key_id else None,
        "size": PAGE_SIZE,
        "version": 1,
    }


def _position(
    codec: SignedCursorCodec, cursor: str | None, binding: dict[str, object]
) -> list[Any] | None:
    if cursor is None:
        return None
    try:
        payload = codec.decode_payload(cursor, required_keys=_CURSOR_KEYS)
        if any(payload[key] != value for key, value in binding.items()):
            raise ValueError
        last = payload["last"]
        if type(last) is not list or not 1 <= len(last) <= 2:
            raise ValueError
        return last
    except ValueError, InvalidSignedCursor:
        raise InvalidSubmissionCursor("Invalid submission cursor") from None


def _uuid(value: object) -> UUID:
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError
        return UUID(value)
    except ValueError, TypeError:
        raise InvalidSubmissionCursor("Invalid submission cursor") from None


def _time(value: object) -> datetime:
    try:
        if type(value) is not str:
            raise ValueError
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except ValueError, TypeError:
        raise InvalidSubmissionCursor("Invalid submission cursor") from None


def _next(
    codec: SignedCursorCodec, binding: dict[str, object], position: list[object], more: bool
) -> str | None:
    return codec.encode_payload({**binding, "last": position}) if more else None


def _group(session: Session, product_id: UUID, group_id: UUID) -> ChangeSet:
    row = session.scalar(
        select(ChangeSet)
        .join(SubmissionBatch)
        .where(ChangeSet.id == group_id, SubmissionBatch.product_id == product_id)
    )
    if row is None:
        raise SubmissionReviewUnavailable("submission unavailable")
    return row


def _source(value: object) -> ChangeSetSource | None:
    if value is None:
        return None
    try:
        return ChangeSetSource.model_validate(value)
    except ValidationError:
        raise SubmissionConflict("invalid_snapshot") from None


def group_metadata(session: Session, row: ChangeSet) -> dict[str, object]:
    actor = session.execute(
        select(User.id, User.display_name)
        .join(SubmissionBatch, SubmissionBatch.actor_id == User.id)
        .where(SubmissionBatch.id == row.batch_id)
    ).one_or_none()
    sources: dict[tuple[UUID, str], ChangeSetSource] = {}
    entries = (
        session.execute(
            select(ChangeSetItem.members[0]["sources"])
            .where(ChangeSetItem.change_set_id == row.id)
            .limit(101)
        )
        .scalars()
        .all()
    )
    available = bool(entries) and len(entries) <= 100
    for raw in entries:
        if type(raw) is not list or not 1 <= len(raw) <= 2:
            available = False
            continue
        for value in raw:
            source = _source(value)
            if source is not None:
                key = (source.mapping_id, source.repository_side)
                if key in sources and sources[key] != source:
                    raise SubmissionConflict("invalid_snapshot")
                sources[key] = source
    started = session.scalar(
        select(func.min(ChangeSetEvent.created_at)).where(
            ChangeSetEvent.change_set_id == row.id,
            ChangeSetEvent.attempt == row.attempt,
            ChangeSetEvent.event_kind == "reauthorization",
            ChangeSetEvent.outcome == "intent",
        )
    )
    return {
        "actor": SubmissionActor(id=actor.id, display_name=actor.display_name) if actor else None,
        "sources": list(sources.values()),
        "provenance_available": available,
        "attempt_started_at": started or row.started_at or row.created_at,
        "finished_at": row.finished_at,
        "branch_commit": row.branch_commit,
        "commit_hash": row.commit_hash,
    }


def list_change_sets(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    cursor_secret: str,
    cursor: str | None = None,
    key_id: UUID | None = None,
) -> ChangeSetHistoryPage:
    with session.begin():
        _, actor = _product_actor(session, product_id, actor_id, action=False)
        codec = SignedCursorCodec(cursor_secret)
        binding = _binding(product_id, actor, "history", None, key_id)
        pos = _position(codec, cursor, binding)
        query = (
            select(ChangeSet).join(SubmissionBatch).where(SubmissionBatch.product_id == product_id)
        )
        if key_id is not None:
            query = query.where(
                select(ChangeSetItem.proposal_id)
                .where(ChangeSetItem.change_set_id == ChangeSet.id, ChangeSetItem.key_id == key_id)
                .exists()
            )
        if pos is not None:
            if len(pos) != 2:
                raise InvalidSubmissionCursor("Invalid submission cursor")
            stamp, identity = _time(pos[0]), _uuid(pos[1])
            if (
                session.scalar(
                    query.where(
                        ChangeSet.id == identity, ChangeSet.created_at == stamp
                    ).with_only_columns(ChangeSet.id)
                )
                is None
            ):
                raise InvalidSubmissionCursor("Invalid submission cursor")
            query = query.where(tuple_(ChangeSet.created_at, ChangeSet.id) < (stamp, identity))
        rows = list(
            session.scalars(
                query.order_by(ChangeSet.created_at.desc(), ChangeSet.id.desc()).limit(
                    PAGE_SIZE + 1
                )
            )
        )
        visible = rows[:PAGE_SIZE]
        return ChangeSetHistoryPage(
            items=[change_set_response(row, session=session, actor_id=actor_id) for row in visible],
            next_cursor=_next(
                codec,
                binding,
                [visible[-1].created_at.isoformat(), str(visible[-1].id)],
                len(rows) > PAGE_SIZE,
            )
            if visible
            else None,
        )


def list_change_set_items(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    change_set_id: UUID,
    cursor_secret: str,
    cursor: str | None = None,
) -> ChangeSetItemsPage:
    with session.begin():
        _, actor = _product_actor(session, product_id, actor_id, action=False)
        _group(session, product_id, change_set_id)
        codec = SignedCursorCodec(cursor_secret)
        binding = _binding(product_id, actor, "items", change_set_id, None)
        pos = _position(codec, cursor, binding)
        after = _uuid(pos[0]) if pos is not None and len(pos) == 1 else None
        if pos is not None and after is None:
            raise InvalidSubmissionCursor("Invalid submission cursor")
        if (
            after is not None
            and session.scalar(
                select(ChangeSetItem.proposal_id).where(
                    ChangeSetItem.change_set_id == change_set_id, ChangeSetItem.proposal_id == after
                )
            )
            is None
        ):
            raise InvalidSubmissionCursor("Invalid submission cursor")
        rows = (
            session.execute(
                text("""
            SELECT i.proposal_id, i.proposal_version, i.key_id, i.language,
                   substr(i.members->0->>'key',1,512) AS key,
                   length(i.members->0->>'key')>512 AS key_truncated,
                   jsonb_array_length(i.members) AS value_count,
                   p.version AS current_version
            FROM change_set_items i LEFT JOIN translation_proposals p
              ON p.id=i.proposal_id AND p.translation_key_id=i.key_id AND p.language=i.language
            WHERE i.change_set_id=:group_id
              AND (CAST(:after_id AS uuid) IS NULL OR i.proposal_id > :after_id)
            ORDER BY i.proposal_id LIMIT 26
        """),
                {"group_id": change_set_id, "after_id": after},
            )
            .mappings()
            .all()
        )
        visible = rows[:PAGE_SIZE]
        return ChangeSetItemsPage(
            items=[
                ChangeSetItemResponse(
                    **dict(row),
                    newer_version_available=row["current_version"] is not None
                    and row["current_version"] > row["proposal_version"],
                )
                for row in visible
            ],
            next_cursor=_next(
                codec, binding, [str(visible[-1]["proposal_id"])], len(rows) > PAGE_SIZE
            )
            if visible
            else None,
        )


def list_change_set_values(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    change_set_id: UUID,
    cursor_secret: str,
    cursor: str | None = None,
) -> ChangeSetValuesPage:
    with session.begin():
        _, actor = _product_actor(session, product_id, actor_id, action=False)
        _group(session, product_id, change_set_id)
        codec = SignedCursorCodec(cursor_secret)
        binding = _binding(product_id, actor, "values", change_set_id, None)
        pos = _position(codec, cursor, binding)
        after_id, after_index = None, 0
        if pos is not None:
            if len(pos) != 2 or type(pos[1]) is not int or not 1 <= pos[1] <= 5000:
                raise InvalidSubmissionCursor("Invalid submission cursor")
            after_id, after_index = _uuid(pos[0]), pos[1]
            length = session.scalar(
                select(func.jsonb_array_length(ChangeSetItem.members)).where(
                    ChangeSetItem.change_set_id == change_set_id,
                    ChangeSetItem.proposal_id == after_id,
                )
            )
            if length is None or after_index > length:
                raise InvalidSubmissionCursor("Invalid submission cursor")
        params = {"group_id": change_set_id, "after_id": after_id, "after_index": after_index}
        coordinates = (
            session.execute(
                text("""
            SELECT i.proposal_id, m.ordinality AS member_index, octet_length(m.value::text) AS size
            FROM change_set_items i
            CROSS JOIN LATERAL jsonb_array_elements(i.members) WITH ORDINALITY m
            WHERE i.change_set_id=:group_id AND
                (CAST(:after_id AS uuid) IS NULL
                 OR (i.proposal_id,m.ordinality) > (:after_id,:after_index))
            ORDER BY i.proposal_id,m.ordinality LIMIT 26
        """),
                params,
            )
            .mappings()
            .all()
        )
        visible, size = [], 0
        for row in coordinates[:PAGE_SIZE]:
            if row["size"] > MAX_PAGE_BYTES:
                raise SubmissionConflict("invalid_snapshot")
            if size + row["size"] > MAX_PAGE_BYTES:
                break
            visible.append(row)
            size += row["size"]
        items = []
        for coordinate in visible:
            row = (
                session.execute(
                    text("""
                SELECT proposal_id, proposal_version, language,
                       members->CAST(:index AS integer) AS member
                FROM change_set_items WHERE change_set_id=:group_id AND proposal_id=:proposal_id
            """),
                    {
                        "group_id": change_set_id,
                        "proposal_id": coordinate["proposal_id"],
                        "index": coordinate["member_index"] - 1,
                    },
                )
                .mappings()
                .one()
            )
            member = row["member"]
            items.append(
                ChangeSetValueResponse(
                    proposal_id=row["proposal_id"],
                    proposal_version=row["proposal_version"],
                    value_id=member["value_id"],
                    key=member["key"],
                    language=row["language"],
                    selector_kind=member["selector_kind"],
                    selector=json.dumps(
                        member["selector"], ensure_ascii=False, separators=(",", ":")
                    ),
                    published_text=member["published_text"],
                    proposed_text=member["proposed_text"],
                    file_path=member["path"],
                    basis_revision_number=member["basis_revision_number"],
                    basis_digest=member["basis_digest"],
                    source=_source(member.get("source")),
                )
            )
        return ChangeSetValuesPage(
            items=items,
            next_cursor=_next(
                codec,
                binding,
                [str(visible[-1]["proposal_id"]), visible[-1]["member_index"]],
                len(coordinates) > len(visible),
            )
            if visible
            else None,
        )


def list_change_set_files(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    change_set_id: UUID,
    cursor_secret: str,
    cursor: str | None = None,
) -> ChangeSetFilesPage:
    with session.begin():
        _, actor = _product_actor(session, product_id, actor_id, action=False)
        _group(session, product_id, change_set_id)
        codec = SignedCursorCodec(cursor_secret)
        binding = _binding(product_id, actor, "files", change_set_id, None)
        pos = _position(codec, cursor, binding)
        after = _uuid(pos[0]) if pos is not None and len(pos) == 1 else None
        if pos is not None and after is None:
            raise InvalidSubmissionCursor("Invalid submission cursor")
        if (
            after is not None
            and session.scalar(
                select(ChangeSetFile.id).where(
                    ChangeSetFile.change_set_id == change_set_id, ChangeSetFile.id == after
                )
            )
            is None
        ):
            raise InvalidSubmissionCursor("Invalid submission cursor")
        rows = (
            session.execute(
                text("""
            SELECT id,path,before_sha256,after_sha256,octet_length(original_bytes) AS before_bytes,
                   octet_length(content) AS after_bytes,attributes
            FROM change_set_files
            WHERE change_set_id=:group_id AND (CAST(:after_id AS uuid) IS NULL OR id > :after_id)
            ORDER BY id LIMIT 26
        """),
                {"group_id": change_set_id, "after_id": after},
            )
            .mappings()
            .all()
        )
        items = []
        for row in rows[:PAGE_SIZE]:
            matches = (
                session.execute(
                    text("""
                WITH members AS (
                    SELECT i.proposal_id,i.language,m.value
                    FROM change_set_items i
                    CROSS JOIN LATERAL jsonb_array_elements(i.members) m(value)
                    WHERE i.change_set_id=:group_id AND m.value->>'path'=:path
                ), counts AS (
                    SELECT count(*) AS member_count,
                        array_agg(DISTINCT value->'file_changed_values')
                            FILTER (WHERE value ? 'file_changed_values') AS frozen_counts,
                        count(DISTINCT jsonb_build_array(language,value->'key',
                            value->'selector_kind',value->'selector'))
                            FILTER (WHERE value->>'published_text'
                                IS DISTINCT FROM value->>'proposed_text') AS legacy_changed_values
                    FROM members
                )
                SELECT m.value->'source' AS source,m.value->>'format' AS format,c.*
                FROM members m CROSS JOIN counts c
                ORDER BY m.proposal_id LIMIT 1
            """),
                    {"group_id": change_set_id, "path": row["path"]},
                )
                .mappings()
                .all()
            )
            match = matches[0] if matches else None
            frozen_counts = match["frozen_counts"] if match else None
            changed_values = (
                frozen_counts[0]
                if frozen_counts
                else match["legacy_changed_values"]
                if match
                else 0
            )
            if (
                (match is not None and match["member_count"] > 5000)
                or (frozen_counts is not None and len(frozen_counts) != 1)
                or type(changed_values) is not int
                or not 0 <= changed_values <= 5000
            ):
                raise SubmissionConflict("invalid_snapshot")
            items.append(
                ChangeSetFileResponse(
                    **dict(row),
                    changed_values=changed_values,
                    source=_source(matches[0]["source"]) if matches else None,
                    format=matches[0]["format"] if matches else None,
                )
            )
        return ChangeSetFilesPage(
            items=items,
            next_cursor=_next(
                codec, binding, [str(rows[PAGE_SIZE - 1]["id"])], len(rows) > PAGE_SIZE
            )
            if len(rows) > PAGE_SIZE
            else None,
        )


def _receipt(
    row: ChangeSet, event: ChangeSetEvent
) -> (
    BranchReceiptResponse
    | CommitReceiptResponse
    | PullRequestReceiptResponse
    | AuthorityReceiptResponse
    | None
):
    data = event.receipt
    try:
        if event.step == "branch" and event.outcome == "verified":
            return BranchReceiptResponse.model_validate(
                {"name": data["name"], "commit_hash": data["commit_hash"]}
            )
        if event.step == "commit" and event.outcome == "verified":
            return CommitReceiptResponse.model_validate(
                {key: data[key] for key in ("commit_hash", "parent", "branch", "manifest_digest")}
            )
        if event.step == "pull_request" and event.outcome == "verified":
            url = data.get("url")
            try:
                if type(url) is not str or type(data.get("id")) is not int:
                    raise ValueError
                validate_pull_request_url(
                    url,
                    workspace=row.workspace,
                    repository_slug=row.repository_slug,
                    pull_request_id=cast(int, data["id"]),
                )
            except ValueError:
                url = None
            return PullRequestReceiptResponse.model_validate(
                {
                    **{
                        key: data[key]
                        for key in (
                            "id",
                            "state",
                            "source_branch",
                            "source_commit",
                            "target_branch",
                            "target_commit",
                        )
                    },
                    "url": url,
                }
            )
        if event.step == "authority":
            action = (
                data.get("action")
                or data.get("reason")
                or (
                    "reauthorized"
                    if event.event_kind == "reauthorization" and event.outcome == "verified"
                    else None
                )
            )
            if action is not None:
                return AuthorityReceiptResponse.model_validate(
                    {
                        "action": action,
                        "actor_id": data.get("actor_id"),
                        "pull_request_id": data.get("pull_request_id"),
                    }
                )
    except KeyError, ValidationError:
        return None
    return None


def list_change_set_activity(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    change_set_id: UUID,
    cursor_secret: str,
    cursor: str | None = None,
) -> ChangeSetActivityPage:
    with session.begin():
        _, actor = _product_actor(session, product_id, actor_id, action=False)
        group = _group(session, product_id, change_set_id)
        codec = SignedCursorCodec(cursor_secret)
        binding = _binding(product_id, actor, "activity", change_set_id, None)
        pos = _position(codec, cursor, binding)
        query = select(ChangeSetEvent).where(ChangeSetEvent.change_set_id == change_set_id)
        if pos is not None:
            if len(pos) != 2:
                raise InvalidSubmissionCursor("Invalid submission cursor")
            stamp, identity = _time(pos[0]), _uuid(pos[1])
            if (
                session.scalar(
                    query.where(
                        ChangeSetEvent.id == identity, ChangeSetEvent.created_at == stamp
                    ).with_only_columns(ChangeSetEvent.id)
                )
                is None
            ):
                raise InvalidSubmissionCursor("Invalid submission cursor")
            query = query.where(
                tuple_(ChangeSetEvent.created_at, ChangeSetEvent.id) < (stamp, identity)
            )
        rows = list(
            session.scalars(
                query.order_by(ChangeSetEvent.created_at.desc(), ChangeSetEvent.id.desc()).limit(
                    PAGE_SIZE + 1
                )
            )
        )
        return ChangeSetActivityPage(
            items=[
                ChangeSetActivityResponse.model_validate(
                    {
                        "id": e.id,
                        "event_kind": e.event_kind,
                        "step": e.step,
                        "outcome": e.outcome,
                        "attempt": e.attempt,
                        "created_at": e.created_at,
                        "receipt": _receipt(group, e),
                    }
                )
                for e in rows[:PAGE_SIZE]
            ],
            next_cursor=_next(
                codec,
                binding,
                [rows[PAGE_SIZE - 1].created_at.isoformat(), str(rows[PAGE_SIZE - 1].id)],
                len(rows) > PAGE_SIZE,
            )
            if len(rows) > PAGE_SIZE
            else None,
        )
