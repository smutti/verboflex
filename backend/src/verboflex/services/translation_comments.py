"""Transactional stable key-language discussion authority."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal
from verboflex.auth.translation_access import (
    TranslationGroupAccessMode,
    resolve_translation_group_access,
)
from verboflex.models.review import (
    Notification,
    NotificationKind,
    TranslationComment,
    TranslationCommentMention,
    TranslationCommentVersion,
)
from verboflex.models.translation import TranslationValue
from verboflex.models.user import User
from verboflex.schemas.comments import MentionInput
from verboflex.schemas.users import RoleName
from verboflex.services.signed_cursor import (
    CursorBinding,
    CursorPosition,
    InvalidSignedCursor,
    SignedCursorCodec,
)

COMMENT_PAGE_SIZE: Final = 5
COMMENT_HISTORY_PAGE_SIZE: Final = 50
MAX_COMMENT_BODY_CHARS: Final = 65_536
ANCHOR_SIDE_SIZE: Final = 5


class TranslationCommentUnavailable(LookupError):
    """Generic missing, foreign, mismatched, or corrupt discussion outcome."""


class TranslationCommentInputInvalid(ValueError):
    """A direct caller supplied a value outside the closed discussion contract."""


class InvalidTranslationCommentCursor(ValueError):
    """A comment cursor failed signature or binding validation."""


class CommentVersionConflict(RuntimeError):
    """The comment head changed after the editor loaded it."""

    def __init__(
        self,
        *,
        attempted_body: str,
        attempted_version: int,
        latest: TranslationCommentProjection,
    ) -> None:
        super().__init__("comment version conflict")
        self.attempted_body = attempted_body
        self.attempted_version = attempted_version
        self.latest = latest


class TranslationCommentActionDenied(PermissionError):
    """The current principal cannot perform the comment-local action."""


@dataclass(frozen=True, slots=True)
class CommentAuthorProjection:
    id: UUID
    display_name: str


@dataclass(frozen=True, slots=True)
class TranslationCommentProjection:
    id: UUID
    translation_group_id: UUID
    language: str
    status: Literal["available", "removed"]
    body: str | None
    mentions: tuple[ValidatedMention, ...]
    author: CommentAuthorProjection
    current_version: int
    edited: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    deleted_by: UUID | None
    new_notification_recipient_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class TranslationCommentPage:
    items: tuple[TranslationCommentProjection, ...]
    older_cursor: str | None


@dataclass(frozen=True, slots=True)
class CommentAnchorWindow:
    target_id: UUID
    items: tuple[TranslationCommentProjection, ...]


@dataclass(frozen=True, slots=True)
class TranslationCommentVersionProjection:
    version: int
    status: Literal["available", "removed"]
    body: str | None
    mentions: tuple[ValidatedMention, ...]
    actor: CommentAuthorProjection
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TranslationCommentVersionPage:
    items: tuple[TranslationCommentVersionProjection, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class _Discussion:
    translation_group_id: UUID
    translation_key_id: UUID
    scope_id: UUID
    language: str


@dataclass(frozen=True, slots=True)
class ValidatedMention:
    user_id: UUID
    start_utf16: int
    end_utf16: int
    display_text: str


def _require_body(value: object) -> str:
    if type(value) is not str or not 1 <= len(value) <= MAX_COMMENT_BODY_CHARS:
        raise TranslationCommentInputInvalid("invalid comment body")
    if not value.strip():
        raise TranslationCommentInputInvalid("invalid comment body")
    return value


def _require_version(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 9_007_199_254_740_991:
        raise TranslationCommentInputInvalid("invalid comment version")
    return value


def _utf16_slice(body: str, start: int, end: int) -> str:
    """Decode one half-open UTF-16 code-unit range without accepting split surrogates."""
    if type(start) is not int or type(end) is not int or start < 0 or end <= start:
        raise TranslationCommentInputInvalid("invalid mention range")
    encoded = body.encode("utf-16-le")
    start_byte = start * 2
    end_byte = end * 2
    if end_byte > len(encoded):
        raise TranslationCommentInputInvalid("invalid mention range")
    try:
        encoded[:start_byte].decode("utf-16-le", errors="strict")
        selected = encoded[start_byte:end_byte].decode("utf-16-le", errors="strict")
        encoded[end_byte:].decode("utf-16-le", errors="strict")
    except UnicodeDecodeError as error:
        raise TranslationCommentInputInvalid("invalid mention range") from error
    return selected


def validate_utf16_mentions(
    session: Session,
    *,
    body: str,
    mentions: Sequence[MentionInput],
) -> tuple[ValidatedMention, ...]:
    """Re-resolve active identities and validate exact non-overlapping browser ranges."""
    validated: list[ValidatedMention] = []
    previous_end = -1
    for mention in sorted(mentions, key=lambda item: (item.start_utf16, item.end_utf16)):
        if mention.start_utf16 < previous_end:
            raise TranslationCommentInputInvalid("invalid mention range")
        selected = _utf16_slice(body, mention.start_utf16, mention.end_utf16)
        user = session.get(User, mention.user_id)
        if user is None or not user.is_active:
            raise TranslationCommentInputInvalid("invalid mention identity")
        expected = f"@{user.display_name}"
        if mention.display_text != expected or selected != expected:
            raise TranslationCommentInputInvalid("invalid mention identity")
        validated.append(
            ValidatedMention(
                user_id=user.id,
                start_utf16=mention.start_utf16,
                end_utf16=mention.end_utf16,
                display_text=selected,
            )
        )
        previous_end = mention.end_utf16
    return tuple(validated)


def _persist_mentions(
    session: Session,
    *,
    comment_version_id: UUID,
    mentions: Sequence[ValidatedMention],
) -> None:
    session.add_all(
        TranslationCommentMention(
            comment_version_id=comment_version_id,
            mentioned_user_id=mention.user_id,
            start_utf16=mention.start_utf16,
            end_utf16=mention.end_utf16,
            display_text=mention.display_text,
        )
        for mention in mentions
    )


def insert_mention_notifications(
    session: Session,
    *,
    comment_id: UUID,
    actor_id: UUID,
    recipient_ids: Sequence[UUID],
) -> tuple[UUID, ...]:
    """Insert durable lifetime-deduped mention notifications in the caller transaction."""
    eligible = tuple(sorted(set(recipient_ids) - {actor_id}, key=str))
    if not eligible:
        return ()
    statement = (
        postgresql_insert(Notification)
        .values(
            [
                {
                    "recipient_user_id": recipient_id,
                    "actor_user_id": actor_id,
                    "originating_comment_id": comment_id,
                    "kind": NotificationKind.MENTION.value,
                }
                for recipient_id in eligible
            ]
        )
        .on_conflict_do_nothing(constraint="uq_notifications_recipient_comment_kind")
        .returning(Notification.recipient_user_id)
    )
    return tuple(sorted(session.scalars(statement), key=str))


def _load_mentions(
    session: Session,
    *,
    comment_version_id: UUID,
) -> tuple[ValidatedMention, ...]:
    rows = tuple(
        session.scalars(
            select(TranslationCommentMention)
            .where(TranslationCommentMention.comment_version_id == comment_version_id)
            .order_by(
                TranslationCommentMention.start_utf16,
                TranslationCommentMention.id,
            )
        )
    )
    return tuple(
        ValidatedMention(
            user_id=row.mentioned_user_id,
            start_utf16=row.start_utf16,
            end_utf16=row.end_utf16,
            display_text=row.display_text,
        )
        for row in rows
    )


def _discussion(
    session: Session,
    *,
    principal: Principal,
    translation_group_id: UUID,
    mode: TranslationGroupAccessMode,
) -> _Discussion:
    access = resolve_translation_group_access(
        session,
        principal=principal,
        translation_group_id=translation_group_id,
        mode=mode,
    )
    anchor = session.get(TranslationValue, access.group.id)
    if (
        anchor is None
        or anchor.id != translation_group_id
        or anchor.language != access.group.language
        or anchor.key.product_id != access.product_id
    ):
        raise TranslationCommentUnavailable("comment unavailable")
    return _Discussion(
        translation_group_id=translation_group_id,
        translation_key_id=anchor.translation_key_id,
        scope_id=anchor.scope_id,
        language=anchor.language,
    )


def _scope(discussion: _Discussion) -> str:
    return f"{discussion.translation_key_id}:{discussion.language}"


def _binding(
    *,
    principal: Principal,
    discussion: _Discussion,
    page_size: int,
    direction: Literal["ascending", "descending"],
) -> CursorBinding:
    return CursorBinding(
        kind="comments",
        principal_id=principal.user_id,
        scope=_scope(discussion),
        filters={"group": str(discussion.translation_group_id), "language": discussion.language},
        page_size=page_size,
        direction=direction,
    )


def _load_user(session: Session, user_id: UUID) -> CommentAuthorProjection:
    user = session.get(User, user_id)
    if user is None:
        raise TranslationCommentUnavailable("comment unavailable")
    return CommentAuthorProjection(id=user.id, display_name=user.display_name)


def _project(
    session: Session,
    *,
    discussion: _Discussion,
    comment: TranslationComment,
    new_notification_recipient_ids: tuple[UUID, ...] = (),
) -> TranslationCommentProjection:
    author = _load_user(session, comment.author_id)
    removed = comment.deleted_at is not None
    body: str | None = None
    mentions: tuple[ValidatedMention, ...] = ()
    if not removed:
        version = session.scalar(
            select(TranslationCommentVersion).where(
                TranslationCommentVersion.comment_id == comment.id,
                TranslationCommentVersion.version_number == comment.current_version,
            )
        )
        if version is None:
            raise TranslationCommentUnavailable("comment unavailable")
        body = version.body
        mentions = _load_mentions(session, comment_version_id=version.id)
    return TranslationCommentProjection(
        id=comment.id,
        translation_group_id=discussion.translation_group_id,
        language=discussion.language,
        status="removed" if removed else "available",
        body=body,
        mentions=mentions,
        author=author,
        current_version=comment.current_version,
        edited=comment.current_version > 1,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        deleted_at=comment.deleted_at,
        deleted_by=comment.deleted_by,
        new_notification_recipient_ids=new_notification_recipient_ids,
    )


def _base_query(discussion: _Discussion) -> Select[tuple[TranslationComment]]:
    return select(TranslationComment).where(
        TranslationComment.translation_key_id == discussion.translation_key_id,
        TranslationComment.scope_id == discussion.scope_id,
        TranslationComment.language == discussion.language,
    )


def _load_scoped_comment(
    session: Session,
    *,
    discussion: _Discussion,
    comment_id: UUID,
    for_update: bool = False,
) -> TranslationComment:
    query = _base_query(discussion).where(TranslationComment.id == comment_id)
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    comment = session.scalar(query)
    if comment is None:
        raise TranslationCommentUnavailable("comment unavailable")
    return comment


def _history_binding(
    *,
    principal: Principal,
    discussion: _Discussion,
    comment_id: UUID,
) -> CursorBinding:
    return CursorBinding(
        kind="comments",
        principal_id=principal.user_id,
        scope=_scope(discussion),
        filters={
            "comment": str(comment_id),
            "group": str(discussion.translation_group_id),
            "language": discussion.language,
        },
        page_size=COMMENT_HISTORY_PAGE_SIZE,
        direction="ascending",
    )


def _version_projection(
    session: Session,
    *,
    version: TranslationCommentVersion,
    removed: bool,
) -> TranslationCommentVersionProjection:
    return TranslationCommentVersionProjection(
        version=version.version_number,
        status="removed" if removed else "available",
        body=None if removed else version.body,
        mentions=() if removed else _load_mentions(session, comment_version_id=version.id),
        actor=_load_user(session, version.author_id),
        created_at=version.created_at,
    )


def create_translation_comment(
    session: Session,
    *,
    principal: Principal,
    translation_group_id: UUID,
    body: object,
    mentions: Sequence[MentionInput] = (),
) -> TranslationCommentProjection:
    """Create one head and immutable initial body in the caller transaction."""
    discussion = _discussion(
        session,
        principal=principal,
        translation_group_id=translation_group_id,
        mode=TranslationGroupAccessMode.COMMENT,
    )
    exact_body = _require_body(body)
    exact_mentions = validate_utf16_mentions(session, body=exact_body, mentions=mentions)
    now = datetime.now(UTC)
    comment = TranslationComment(
        scope_id=discussion.scope_id,
        translation_key_id=discussion.translation_key_id,
        language=discussion.language,
        author_id=principal.user_id,
        current_version=1,
        created_at=now,
        updated_at=now,
    )
    session.add(comment)
    session.flush()
    version = TranslationCommentVersion(
        comment_id=comment.id,
        translation_key_id=discussion.translation_key_id,
        language=discussion.language,
        version_number=1,
        body=exact_body,
        author_id=principal.user_id,
        created_at=now,
    )
    session.add(version)
    session.flush()
    _persist_mentions(
        session,
        comment_version_id=version.id,
        mentions=exact_mentions,
    )
    session.flush()
    inserted_recipient_ids = insert_mention_notifications(
        session,
        comment_id=comment.id,
        actor_id=principal.user_id,
        recipient_ids=tuple(mention.user_id for mention in exact_mentions),
    )
    return _project(
        session,
        discussion=discussion,
        comment=comment,
        new_notification_recipient_ids=inserted_recipient_ids,
    )


def list_translation_comments(
    session: Session,
    *,
    principal: Principal,
    translation_group_id: UUID,
    cursor: str | None,
    cursor_secret: str,
) -> TranslationCommentPage:
    """Return newest five in conversation order plus a signed older boundary."""
    discussion = _discussion(
        session,
        principal=principal,
        translation_group_id=translation_group_id,
        mode=TranslationGroupAccessMode.READ,
    )
    binding = _binding(
        principal=principal,
        discussion=discussion,
        page_size=COMMENT_PAGE_SIZE,
        direction="descending",
    )
    query = _base_query(discussion)
    if cursor is not None:
        try:
            position = SignedCursorCodec(cursor_secret).decode(cursor, binding=binding)
        except InvalidSignedCursor as error:
            raise InvalidTranslationCommentCursor("invalid comment cursor") from error
        query = query.where(
            or_(
                TranslationComment.created_at < position.created_at,
                and_(
                    TranslationComment.created_at == position.created_at,
                    TranslationComment.id < position.id,
                ),
            )
        )
    rows = tuple(
        session.scalars(
            query.order_by(
                TranslationComment.created_at.desc(), TranslationComment.id.desc()
            ).limit(COMMENT_PAGE_SIZE + 1)
        )
    )
    visible = rows[:COMMENT_PAGE_SIZE]
    older_cursor = None
    if len(rows) > COMMENT_PAGE_SIZE and visible:
        last = visible[-1]
        older_cursor = SignedCursorCodec(cursor_secret).encode(
            binding=binding,
            position=CursorPosition(created_at=last.created_at, id=last.id),
        )
    return TranslationCommentPage(
        items=tuple(
            _project(session, discussion=discussion, comment=comment)
            for comment in reversed(visible)
        ),
        older_cursor=older_cursor,
    )


def get_translation_comment_anchor(
    session: Session,
    *,
    principal: Principal,
    translation_group_id: UUID,
    comment_id: UUID,
) -> CommentAnchorWindow:
    """Return a fixed target-centered chronological window without collection walking."""
    discussion = _discussion(
        session,
        principal=principal,
        translation_group_id=translation_group_id,
        mode=TranslationGroupAccessMode.READ,
    )
    target = session.scalar(_base_query(discussion).where(TranslationComment.id == comment_id))
    if target is None:
        raise TranslationCommentUnavailable("comment unavailable")
    older_predicate = or_(
        TranslationComment.created_at < target.created_at,
        and_(
            TranslationComment.created_at == target.created_at,
            TranslationComment.id < target.id,
        ),
    )
    newer_predicate = or_(
        TranslationComment.created_at > target.created_at,
        and_(
            TranslationComment.created_at == target.created_at,
            TranslationComment.id > target.id,
        ),
    )
    older_desc = tuple(
        session.scalars(
            _base_query(discussion)
            .where(older_predicate)
            .order_by(TranslationComment.created_at.desc(), TranslationComment.id.desc())
            .limit(ANCHOR_SIDE_SIZE)
        )
    )
    newer = tuple(
        session.scalars(
            _base_query(discussion)
            .where(newer_predicate)
            .order_by(TranslationComment.created_at, TranslationComment.id)
            .limit(ANCHOR_SIDE_SIZE)
        )
    )
    window = (*reversed(older_desc), target, *newer)
    return CommentAnchorWindow(
        target_id=target.id,
        items=tuple(
            _project(session, discussion=discussion, comment=comment) for comment in window
        ),
    )


def edit_translation_comment(
    session: Session,
    *,
    principal: Principal,
    translation_group_id: UUID,
    comment_id: UUID,
    body: object,
    expected_version: object,
    mentions: Sequence[MentionInput] = (),
) -> TranslationCommentProjection:
    """Append one author edit after locking and comparing the exact head version."""
    discussion = _discussion(
        session,
        principal=principal,
        translation_group_id=translation_group_id,
        mode=TranslationGroupAccessMode.COMMENT,
    )
    comment = _load_scoped_comment(
        session,
        discussion=discussion,
        comment_id=comment_id,
        for_update=True,
    )
    if comment.deleted_at is not None:
        raise TranslationCommentUnavailable("comment unavailable")
    if comment.author_id != principal.user_id:
        raise TranslationCommentActionDenied("comment action denied")
    exact_body = _require_body(body)
    exact_mentions = validate_utf16_mentions(session, body=exact_body, mentions=mentions)
    exact_version = _require_version(expected_version)
    if comment.current_version != exact_version:
        raise CommentVersionConflict(
            attempted_body=exact_body,
            attempted_version=exact_version,
            latest=_project(session, discussion=discussion, comment=comment),
        )

    next_version = comment.current_version + 1
    _require_version(next_version)
    now = datetime.now(UTC)
    version = TranslationCommentVersion(
        comment_id=comment.id,
        translation_key_id=discussion.translation_key_id,
        language=discussion.language,
        version_number=next_version,
        body=exact_body,
        author_id=principal.user_id,
        created_at=now,
    )
    session.add(version)
    comment.current_version = next_version
    comment.updated_at = now
    session.flush()
    _persist_mentions(
        session,
        comment_version_id=version.id,
        mentions=exact_mentions,
    )
    session.flush()
    inserted_recipient_ids = insert_mention_notifications(
        session,
        comment_id=comment.id,
        actor_id=principal.user_id,
        recipient_ids=tuple(mention.user_id for mention in exact_mentions),
    )
    return _project(
        session,
        discussion=discussion,
        comment=comment,
        new_notification_recipient_ids=inserted_recipient_ids,
    )


def delete_translation_comment(
    session: Session,
    *,
    principal: Principal,
    translation_group_id: UUID,
    comment_id: UUID,
) -> TranslationCommentProjection:
    """Append fixed deletion evidence and retain the stable comment head."""
    discussion = _discussion(
        session,
        principal=principal,
        translation_group_id=translation_group_id,
        mode=TranslationGroupAccessMode.DELETE_COMMENT,
    )
    comment = _load_scoped_comment(
        session,
        discussion=discussion,
        comment_id=comment_id,
        for_update=True,
    )
    if comment.deleted_at is not None:
        raise TranslationCommentUnavailable("comment unavailable")

    next_version = comment.current_version + 1
    _require_version(next_version)
    now = datetime.now(UTC)
    session.add(
        TranslationCommentVersion(
            comment_id=comment.id,
            translation_key_id=discussion.translation_key_id,
            language=discussion.language,
            version_number=next_version,
            body="Comment removed",
            author_id=principal.user_id,
            created_at=now,
        )
    )
    comment.current_version = next_version
    comment.deleted_at = now
    comment.deleted_by = principal.user_id
    comment.updated_at = now
    session.flush()
    return _project(session, discussion=discussion, comment=comment)


def list_comment_versions(
    session: Session,
    *,
    principal: Principal,
    translation_group_id: UUID,
    comment_id: UUID,
    cursor: str | None,
    cursor_secret: str,
) -> TranslationCommentVersionPage:
    """Return live audit history, or a body-free tombstone to ordinary readers."""
    discussion = _discussion(
        session,
        principal=principal,
        translation_group_id=translation_group_id,
        mode=TranslationGroupAccessMode.READ,
    )
    comment = _load_scoped_comment(
        session,
        discussion=discussion,
        comment_id=comment_id,
    )
    is_admin = RoleName.ADMIN in principal.roles
    if comment.deleted_at is not None and not is_admin:
        if cursor is not None:
            raise InvalidTranslationCommentCursor("invalid comment cursor")
        if comment.deleted_by is None or comment.deleted_at is None:
            raise TranslationCommentUnavailable("comment unavailable")
        return TranslationCommentVersionPage(
            items=(
                TranslationCommentVersionProjection(
                    version=comment.current_version,
                    status="removed",
                    body=None,
                    mentions=(),
                    actor=_load_user(session, comment.deleted_by),
                    created_at=comment.updated_at,
                ),
            ),
            next_cursor=None,
        )

    binding = _history_binding(
        principal=principal,
        discussion=discussion,
        comment_id=comment.id,
    )
    query = select(TranslationCommentVersion).where(
        TranslationCommentVersion.comment_id == comment.id,
        TranslationCommentVersion.translation_key_id == discussion.translation_key_id,
        TranslationCommentVersion.language == discussion.language,
    )
    if cursor is not None:
        try:
            position = SignedCursorCodec(cursor_secret).decode(cursor, binding=binding)
        except InvalidSignedCursor as error:
            raise InvalidTranslationCommentCursor("invalid comment cursor") from error
        query = query.where(
            or_(
                TranslationCommentVersion.created_at > position.created_at,
                and_(
                    TranslationCommentVersion.created_at == position.created_at,
                    TranslationCommentVersion.id > position.id,
                ),
            )
        )
    rows = tuple(
        session.scalars(
            query.order_by(
                TranslationCommentVersion.created_at,
                TranslationCommentVersion.id,
            ).limit(COMMENT_HISTORY_PAGE_SIZE + 1)
        )
    )
    visible = rows[:COMMENT_HISTORY_PAGE_SIZE]
    next_cursor = None
    if len(rows) > COMMENT_HISTORY_PAGE_SIZE and visible:
        last = visible[-1]
        next_cursor = SignedCursorCodec(cursor_secret).encode(
            binding=binding,
            position=CursorPosition(created_at=last.created_at, id=last.id),
        )
    return TranslationCommentVersionPage(
        items=tuple(
            _version_projection(
                session,
                version=version,
                removed=(
                    comment.deleted_at is not None
                    and version.version_number == comment.current_version
                ),
            )
            for version in visible
        ),
        next_cursor=next_cursor,
    )
