"""Principal-owned durable notification reads and mutations."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated, Final, Literal, Protocol, cast
from uuid import UUID

from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from verboflex.auth.principal import Principal
from verboflex.auth.translation_access import (
    TranslationGroupAccessMode,
    TranslationGroupAccessUnavailable,
    resolve_translation_group_access,
)
from verboflex.core.config import Settings, get_settings
from verboflex.models.review import Notification, NotificationKind, TranslationComment
from verboflex.models.translation import TranslationValue
from verboflex.models.user import User
from verboflex.services.signed_cursor import (
    CursorBinding,
    CursorPosition,
    InvalidSignedCursor,
    SignedCursorCodec,
)
from verboflex.services.translation_search import get_translation_options

NOTIFICATION_PAGE_SIZE: Final = 25
RECENT_NOTIFICATION_SIZE: Final = 5
MAX_KEY_EXCERPT_CHARS: Final = 200
NOTIFICATION_RECONNECT_MILLISECONDS: Final = 5_000
NOTIFICATION_HEARTBEAT_SECONDS: Final = 15.0
NOTIFICATION_CHANNEL_PREFIX: Final = "verboflex:notification-invalidation"
NotificationView = Literal["all", "unread"]
NotificationCommentStatus = Literal["available", "removed"]


class NotificationUnavailable(LookupError):
    """Generic foreign, absent, inactive-product, or stale notification outcome."""


class InvalidNotificationCursor(ValueError):
    """A notification cursor failed signature or exact binding validation."""


@dataclass(frozen=True, slots=True)
class NotificationInvalidation:
    """Closed content-free Redis/SSE wake-up payload."""

    kind: Literal["notifications_changed"]
    id: str


class NotificationPubSub(Protocol):
    async def subscribe(self, channel: str) -> None: ...

    async def get_message(
        self,
        *,
        ignore_subscribe_messages: bool,
        timeout: float,
    ) -> Mapping[str, object] | None: ...

    async def unsubscribe(self, channel: str) -> None: ...

    async def aclose(self) -> None: ...


class NotificationRedisClient(Protocol):
    async def incr(self, key: str) -> int: ...

    async def publish(self, channel: str, payload: str) -> int: ...

    def pubsub(self) -> NotificationPubSub: ...

    async def aclose(self) -> None: ...


@dataclass(frozen=True, slots=True)
class NotificationActor:
    user_id: UUID
    display_name: str


@dataclass(frozen=True, slots=True)
class NotificationProduct:
    id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class NotificationItem:
    id: UUID
    is_read: bool
    read_at: datetime | None
    created_at: datetime
    actor: NotificationActor
    product: NotificationProduct
    key_excerpt: str
    language: str
    translation_group_id: UUID
    originating_comment_id: UUID
    comment_status: NotificationCommentStatus


@dataclass(frozen=True, slots=True)
class NotificationPage:
    items: tuple[NotificationItem, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class NotificationReadResult:
    item: NotificationItem
    unread_count: int


async def get_notification_redis_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[NotificationRedisClient]:
    """Build one request-owned decoded async Redis client."""
    client = cast(
        NotificationRedisClient,
        Redis.from_url(
            str(settings.redis_url),
            decode_responses=True,
            socket_connect_timeout=settings.service_probe_timeout_seconds,
            socket_timeout=settings.service_probe_timeout_seconds,
        ),
    )
    try:
        yield client
    finally:
        with suppress(RedisError):
            await client.aclose()


def _notification_channel(user_id: UUID) -> str:
    """Derive a non-reversible internal channel without exposing the user UUID."""
    digest = sha256(user_id.bytes).hexdigest()
    return f"{NOTIFICATION_CHANNEL_PREFIX}:{digest}"


def _notification_counter_key(channel: str) -> str:
    return f"{channel}:sequence"


def _invalidation_payload(event: NotificationInvalidation) -> str:
    return json.dumps(
        {"kind": event.kind, "id": event.id},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _decode_invalidation(value: object) -> NotificationInvalidation | None:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return None
    if not isinstance(value, str) or len(value) > 256:
        return None
    try:
        payload = json.loads(value)
    except TypeError, ValueError:
        return None
    if not isinstance(payload, dict) or set(payload) != {"id", "kind"}:
        return None
    event_id = payload.get("id")
    if (
        payload.get("kind") != "notifications_changed"
        or not isinstance(event_id, str)
        or not event_id.isdecimal()
        or not 1 <= len(event_id) <= 64
        or int(event_id) < 1
    ):
        return None
    return NotificationInvalidation(kind="notifications_changed", id=event_id)


async def publish_notification_invalidations(
    redis_client: NotificationRedisClient,
    *,
    recipient_ids: tuple[UUID, ...],
) -> None:
    """Wake only recipients durably inserted by the caller transaction."""
    for recipient_id in sorted(set(recipient_ids), key=str):
        channel = _notification_channel(recipient_id)
        sequence = await redis_client.incr(_notification_counter_key(channel))
        if type(sequence) is not int or sequence < 1:
            raise RuntimeError("notification invalidation sequence unavailable")
        event = NotificationInvalidation(
            kind="notifications_changed",
            id=str(sequence),
        )
        await redis_client.publish(channel, _invalidation_payload(event))


async def stream_notification_invalidations(
    redis_client: NotificationRedisClient,
    *,
    principal: Principal,
    request: Request,
    heartbeat_seconds: float = NOTIFICATION_HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """Yield only principal-channel invalidations and content-free heartbeats."""
    if heartbeat_seconds <= 0:
        raise ValueError("notification heartbeat must be positive")
    channel = _notification_channel(principal.user_id)
    pubsub = redis_client.pubsub()
    subscribed = False
    try:
        await pubsub.subscribe(channel)
        subscribed = True
        yield f"retry: {NOTIFICATION_RECONNECT_MILLISECONDS}\n\n"
        while not await request.is_disconnected():
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=heartbeat_seconds,
            )
            if message is None:
                yield ": heartbeat\n\n"
                continue
            if message.get("type") != "message":
                continue
            event = _decode_invalidation(message.get("data"))
            if event is None:
                continue
            payload = _invalidation_payload(event)
            yield (f"id: {event.id}\nevent: notification-invalidation\ndata: {payload}\n\n")
    except RedisError:
        # HTTP reconciliation remains authoritative; never serialize broker details.
        yield ": heartbeat\n\n"
    finally:
        if subscribed:
            with suppress(RedisError):
                await pubsub.unsubscribe(channel)
        with suppress(RedisError):
            await pubsub.aclose()
        with suppress(RedisError):
            await redis_client.aclose()


def _binding(
    *,
    principal: Principal,
    view: NotificationView,
    product_id: UUID | None,
    page_size: int,
) -> CursorBinding:
    return CursorBinding(
        kind="notifications",
        principal_id=principal.user_id,
        scope="personal-notifications",
        filters={
            "product_id": str(product_id) if product_id is not None else None,
            "view": view,
        },
        page_size=page_size,
        direction="descending",
        version=1,
    )


def _validate_product_filter(
    session: Session, *, product_id: UUID | None, principal_id: UUID
) -> None:
    if product_id is None:
        return
    options = get_translation_options(session, principal_id=principal_id)
    if all(option.id != product_id for option in options.products):
        raise NotificationUnavailable("notification unavailable")


def _group_id_for_comment(session: Session, *, comment: TranslationComment) -> UUID:
    group_id = session.scalar(
        select(TranslationValue.id)
        .where(
            TranslationValue.translation_key_id == comment.translation_key_id,
            TranslationValue.language == comment.language,
        )
        .order_by(TranslationValue.id)
        .limit(1)
    )
    if group_id is None:
        raise NotificationUnavailable("notification unavailable")
    return group_id


def _project(
    session: Session,
    *,
    principal: Principal,
    notification: Notification,
) -> NotificationItem:
    if notification.recipient_user_id != principal.user_id:
        raise NotificationUnavailable("notification unavailable")
    comment = session.get(TranslationComment, notification.originating_comment_id)
    actor = session.get(User, notification.actor_user_id)
    if comment is None or actor is None:
        raise NotificationUnavailable("notification unavailable")
    group_id = _group_id_for_comment(session, comment=comment)
    try:
        access = resolve_translation_group_access(
            session,
            principal=principal,
            translation_group_id=group_id,
            mode=TranslationGroupAccessMode.READ,
        )
    except TranslationGroupAccessUnavailable as error:
        raise NotificationUnavailable("notification unavailable") from error
    excerpt = access.group.raw_key[:MAX_KEY_EXCERPT_CHARS]
    if not excerpt:
        raise NotificationUnavailable("notification unavailable")
    return NotificationItem(
        id=notification.id,
        is_read=notification.read_at is not None,
        read_at=notification.read_at,
        created_at=notification.created_at,
        actor=NotificationActor(user_id=actor.id, display_name=actor.display_name),
        product=NotificationProduct(id=access.product_id, name=access.group.product_name),
        key_excerpt=excerpt,
        language=comment.language,
        translation_group_id=access.group.id,
        originating_comment_id=comment.id,
        comment_status="removed" if comment.deleted_at is not None else "available",
    )


def _owned_query(*, principal: Principal, unread_only: bool) -> Select[tuple[Notification]]:
    query = select(Notification).where(Notification.recipient_user_id == principal.user_id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return query


def _position_predicate(position: CursorPosition) -> ColumnElement[bool]:
    return or_(
        Notification.created_at < position.created_at,
        and_(
            Notification.created_at == position.created_at,
            Notification.id < position.id,
        ),
    )


def _visible_items(
    session: Session,
    *,
    principal: Principal,
    view: NotificationView,
    product_id: UUID | None,
    position: CursorPosition | None,
) -> tuple[NotificationItem, ...]:
    query = _owned_query(principal=principal, unread_only=view == "unread")
    if position is not None:
        query = query.where(_position_predicate(position))
    notifications = tuple(
        session.scalars(query.order_by(Notification.created_at.desc(), Notification.id.desc()))
    )
    visible: list[NotificationItem] = []
    for notification in notifications:
        try:
            item = _project(session, principal=principal, notification=notification)
        except NotificationUnavailable:
            continue
        if product_id is None or item.product.id == product_id:
            visible.append(item)
    return tuple(visible)


def list_notifications(
    session: Session,
    *,
    principal: Principal,
    view: NotificationView = "all",
    product_id: UUID | None = None,
    cursor: str | None = None,
    cursor_secret: str,
) -> NotificationPage:
    """Return one private 25-item page in stable newest-first order."""
    _validate_product_filter(session, product_id=product_id, principal_id=principal.user_id)
    binding = _binding(
        principal=principal,
        view=view,
        product_id=product_id,
        page_size=NOTIFICATION_PAGE_SIZE,
    )
    position = None
    if cursor is not None:
        try:
            position = SignedCursorCodec(cursor_secret).decode(cursor, binding=binding)
        except InvalidSignedCursor as error:
            raise InvalidNotificationCursor("invalid notification cursor") from error
    items = _visible_items(
        session,
        principal=principal,
        view=view,
        product_id=product_id,
        position=position,
    )
    visible = items[:NOTIFICATION_PAGE_SIZE]
    next_cursor = None
    if len(items) > NOTIFICATION_PAGE_SIZE and visible:
        last = visible[-1]
        next_cursor = SignedCursorCodec(cursor_secret).encode(
            binding=binding,
            position=CursorPosition(created_at=last.created_at, id=last.id),
        )
    return NotificationPage(items=visible, next_cursor=next_cursor)


def list_recent_notifications(
    session: Session,
    *,
    principal: Principal,
) -> NotificationPage:
    """Return the newest five visible personal notifications without mutating them."""
    items = _visible_items(
        session,
        principal=principal,
        view="all",
        product_id=None,
        position=None,
    )
    return NotificationPage(items=items[:RECENT_NOTIFICATION_SIZE], next_cursor=None)


def get_unread_notification_count(
    session: Session,
    *,
    principal: Principal,
) -> int:
    """Return the exact non-negative count of visible unread personal notifications."""
    count = len(
        _visible_items(
            session,
            principal=principal,
            view="unread",
            product_id=None,
            position=None,
        )
    )
    if count < 0:  # Defensive closed integer contract.
        raise RuntimeError("invalid notification count")  # pragma: no cover - len() is nonnegative
    return count


def _mark_owned_notification(
    session: Session,
    *,
    principal: Principal,
    query: Select[tuple[Notification]],
) -> NotificationReadResult:
    notification = session.scalar(query.with_for_update())
    if notification is None:
        raise NotificationUnavailable("notification unavailable")
    # Authorization is re-established before any read-state mutation.
    _project(session, principal=principal, notification=notification)
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        session.flush()
    return NotificationReadResult(
        item=_project(session, principal=principal, notification=notification),
        unread_count=get_unread_notification_count(session, principal=principal),
    )


def mark_notification_read(
    session: Session,
    *,
    principal: Principal,
    notification_id: UUID,
) -> NotificationReadResult:
    """Mark only the authenticated principal's exact item read."""
    return _mark_owned_notification(
        session,
        principal=principal,
        query=select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_user_id == principal.user_id,
        ),
    )


def mark_notification_read_by_comment(
    session: Session,
    *,
    principal: Principal,
    comment_id: UUID,
) -> NotificationReadResult:
    """Mark the principal's own mention notification for one opaque comment ID."""
    return _mark_owned_notification(
        session,
        principal=principal,
        query=select(Notification).where(
            Notification.originating_comment_id == comment_id,
            Notification.kind == NotificationKind.MENTION.value,
            Notification.recipient_user_id == principal.user_id,
        ),
    )
