"""Bounded SQL feeds over durable activity; no domain writes or provider I/O."""

import re
from datetime import datetime

from pydantic import TypeAdapter
from sqlalchemy import text
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal
from verboflex.auth.product_access import visible_product_sql
from verboflex.schemas.dashboard import (
    DashboardEvent,
    DashboardFeed,
    DashboardResponse,
    ProjectUpdatesPage,
)
from verboflex.schemas.users import RoleName
from verboflex.services.signed_cursor import InvalidSignedCursor, SignedCursorCodec

FEED_SIZE = 3
_EVENT_ADAPTER: TypeAdapter[DashboardEvent] = TypeAdapter(DashboardEvent)

# Match translation_search's READ boundary, including retained baselines and
# deleted-but-readable translation groups. A key UUID is never a group UUID.
_READABLE_GROUPS = f"""
SELECT DISTINCT ON (key.id, value.language)
       key.id AS key_id, scope.id AS scope_id, value.language,
       value.id AS group_id, left(key.raw_key, 160) AS key_excerpt,
       product.id AS product_id, product.display_name AS product_name
FROM products AS product
JOIN localization_scopes AS scope
  ON scope.product_id = product.id AND scope.active_execution_id IS NOT NULL
JOIN translation_keys AS key
  ON key.scope_id = scope.id AND key.product_id = product.id
JOIN translation_values AS value
  ON value.translation_key_id = key.id AND value.scope_id = scope.id
WHERE product.is_active AND product.deleted_at IS NULL AND {visible_product_sql(actor=":actor_id")}
ORDER BY key.id, value.language, value.id
"""

_REVIEW_EVENTS = """
SELECT 'review:' || activity.id::text AS event_id, activity.created_at AS occurred_at,
       activity.actor_id,
       jsonb_build_object(
           'event_id', 'review:' || activity.id::text,
           'kind', activity.kind, 'occurred_at', activity.created_at,
           'product', jsonb_build_object('id', group_row.product_id,
                                         'name', group_row.product_name),
           'actor', jsonb_build_object('id', actor.id, 'display_name', actor.display_name),
           'translation_group_id', group_row.group_id,
           'language', group_row.language, 'key_excerpt', group_row.key_excerpt,
           'from_state', CASE WHEN activity.kind = 'state_changed' THEN activity.from_state END,
           'to_state', CASE WHEN activity.kind = 'state_changed' THEN activity.to_state END
       ) AS item
FROM review_activities AS activity
JOIN translation_proposals AS proposal
  ON proposal.id = activity.proposal_id
 AND proposal.translation_key_id = activity.translation_key_id
 AND proposal.language = activity.language
JOIN readable_groups AS group_row
  ON group_row.key_id = activity.translation_key_id
 AND group_row.scope_id = proposal.scope_id AND group_row.language = activity.language
JOIN users AS actor ON actor.id = activity.actor_id
WHERE activity.kind IN ('proposal_saved', 'state_changed')
  AND (NOT :personal OR activity.actor_id = :actor_id)
"""

_COMMENT_EVENTS = """
SELECT 'comment-version:' || version.id::text AS event_id, version.created_at AS occurred_at,
       version.author_id AS actor_id,
       jsonb_build_object(
           'event_id', 'comment-version:' || version.id::text,
           'kind', CASE
               WHEN comment.deleted_at IS NOT NULL
                    AND version.version_number = comment.current_version THEN 'comment_removed'
               WHEN version.version_number = 1 THEN 'comment_created'
               ELSE 'comment_edited' END,
           'occurred_at', version.created_at,
           'product', jsonb_build_object('id', group_row.product_id,
                                         'name', group_row.product_name),
           'actor', jsonb_build_object('id', actor.id, 'display_name', actor.display_name),
           'translation_group_id', group_row.group_id,
           'language', group_row.language, 'key_excerpt', group_row.key_excerpt,
           'comment_id', CASE WHEN comment.deleted_at IS NULL THEN comment.id END,
           'comment_status', CASE WHEN comment.deleted_at IS NULL
                                  THEN 'available' ELSE 'removed' END
       ) AS item
FROM translation_comment_versions AS version
JOIN translation_comments AS comment
  ON comment.id = version.comment_id
 AND comment.translation_key_id = version.translation_key_id
 AND comment.language = version.language
JOIN readable_groups AS group_row
  ON group_row.key_id = comment.translation_key_id
 AND group_row.scope_id = comment.scope_id AND group_row.language = comment.language
JOIN users AS actor ON actor.id = version.author_id
WHERE NOT :personal OR version.author_id = :actor_id
"""

# History authorizes the current product, not the immutable batch's revision.
_SUBMISSION_EVENTS = f"""
SELECT 'change-set:' || change_set.id::text AS event_id, change_set.created_at AS occurred_at,
       batch.actor_id,
       jsonb_build_object(
           'event_id', 'change-set:' || change_set.id::text,
           'kind', 'change_set_submitted', 'occurred_at', change_set.created_at,
           'product', jsonb_build_object('id', product.id, 'name', product.display_name),
           'actor', jsonb_build_object('id', actor.id, 'display_name', actor.display_name),
           'change_set_id', change_set.id, 'current_status', change_set.status
       ) AS item
FROM change_sets AS change_set
JOIN submission_batches AS batch ON batch.id = change_set.batch_id
JOIN products AS product ON product.id = batch.product_id
JOIN users AS actor ON actor.id = batch.actor_id
WHERE product.is_active AND product.deleted_at IS NULL AND {visible_product_sql(actor=":actor_id")}
  AND product.active_revision_id IS NOT NULL
  AND (NOT :personal OR batch.actor_id = :actor_id)
"""

_IMPORT_EVENTS = f"""
SELECT DISTINCT 'import:' || product.id::text || ':' || execution.id::text AS event_id,
       execution.finished_at AS occurred_at, NULL::uuid AS actor_id,
       jsonb_build_object(
           'event_id', 'import:' || product.id::text || ':' || execution.id::text,
           'kind', 'current_import_completed', 'occurred_at', execution.finished_at,
           'product', jsonb_build_object('id', product.id, 'name', product.display_name),
           'actor', NULL
       ) AS item
FROM products AS product
JOIN localization_scopes AS scope ON scope.product_id = product.id
JOIN import_jobs AS job
  ON job.id = scope.active_import_job_id AND job.product_id = scope.product_id
 AND job.mapping_id = scope.current_mapping_id
JOIN import_executions AS execution
  ON execution.id = scope.active_execution_id AND execution.import_job_id = job.id
WHERE product.is_active AND product.deleted_at IS NULL AND {visible_product_sql(actor=":actor_id")}
  AND execution.state = 'succeeded' AND execution.finished_at IS NOT NULL
  AND NOT :personal
"""

_EVENTS_SQL = f"""
WITH readable_groups AS ({_READABLE_GROUPS}), events AS (
    {_REVIEW_EVENTS}
    UNION ALL
    {_COMMENT_EVENTS}
    UNION ALL
    {_SUBMISSION_EVENTS}
    UNION ALL
    {_IMPORT_EVENTS}
)
"""
_FEED_SQL = text(
    _EVENTS_SQL
    + """
SELECT item FROM events
ORDER BY occurred_at DESC, event_id COLLATE "C" DESC
LIMIT :lookahead
"""
)
_PROJECT_UPDATES_SQL = text(
    _EVENTS_SQL
    + """
SELECT item FROM events
WHERE CAST(:before_time AS timestamptz) IS NULL
   OR occurred_at < CAST(:before_time AS timestamptz)
   OR (occurred_at = CAST(:before_time AS timestamptz)
       AND event_id COLLATE "C" < CAST(:before_id AS text) COLLATE "C")
ORDER BY occurred_at DESC, event_id COLLATE "C" DESC
LIMIT :lookahead
"""
)


def get_personal_dashboard(session: Session, *, principal: Principal) -> DashboardResponse:
    """Derive private ownership from validated authority before each bounded SELECT."""
    if not principal.roles or not set(principal.roles) <= set(RoleName):
        raise PermissionError("dashboard action denied")

    def feed(*, personal: bool) -> DashboardFeed:
        rows = (
            session.execute(
                _FEED_SQL,
                {"personal": personal, "actor_id": principal.user_id, "lookahead": FEED_SIZE + 1},
            )
            .scalars()
            .all()
        )
        return DashboardFeed(
            items=[_EVENT_ADAPTER.validate_python(row) for row in rows[:FEED_SIZE]],
            has_more=len(rows) > FEED_SIZE,
        )

    return DashboardResponse(my_activity=feed(personal=True), project_updates=feed(personal=False))


def get_project_updates(
    session: Session,
    *,
    principal: Principal,
    cursor: str | None,
    secret: str,
    personal: bool = False,
) -> ProjectUpdatesPage:
    """Page a personal or project feed with a signed caller- and feed-bound keyset."""
    if not principal.roles or not set(principal.roles) <= set(RoleName):
        raise PermissionError("dashboard action denied")
    codec = SignedCursorCodec(secret)
    binding = {
        "v": 1,
        "scope": "my_activity" if personal else "project_updates",
        "principal": str(principal.user_id),
        "roles": sorted(principal.roles),
    }
    before_time, before_id = None, None
    if cursor is not None:
        payload = codec.decode_payload(cursor, required_keys=frozenset((*binding, "time", "event")))
        try:
            if (
                any(payload[key] != value for key, value in binding.items())
                or type(payload["v"]) is not int
            ):
                raise ValueError
            if not isinstance(payload["time"], str) or not isinstance(payload["event"], str):
                raise ValueError
            before_time = datetime.fromisoformat(payload["time"])
            before_id = payload["event"]
            if before_time.tzinfo is None or not re.fullmatch(r"[a-z0-9:-]{1,100}", before_id):
                raise ValueError
        except KeyError, ValueError, TypeError:
            raise InvalidSignedCursor("invalid cursor") from None
    rows = (
        session.execute(
            _PROJECT_UPDATES_SQL,
            {
                "personal": personal,
                "actor_id": principal.user_id,
                "lookahead": 21,
                "before_time": before_time,
                "before_id": before_id,
            },
        )
        .scalars()
        .all()
    )
    items = [_EVENT_ADAPTER.validate_python(row) for row in rows[:20]]
    next_cursor = None
    if len(rows) > 20:
        last = items[-1]
        next_cursor = codec.encode_payload(
            {**binding, "time": last.occurred_at.isoformat(), "event": last.event_id}
        )
    return ProjectUpdatesPage(items=items, next_cursor=next_cursor)
