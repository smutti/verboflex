"""Durable pending review, discussion, mention, and notification identities."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verboflex.db.base import Base
from verboflex.models.translation import ReviewState


class ReviewActivityKind(StrEnum):
    """Closed review-audit event vocabulary."""

    PROPOSAL_SAVED = "proposal_saved"
    STATE_CHANGED = "state_changed"


class NotificationKind(StrEnum):
    """Closed v1 personal-notification vocabulary."""

    MENTION = "mention"


def _enum_check(column: str, vocabulary: type[StrEnum]) -> str:
    values = ", ".join(f"'{member.value}'" for member in vocabulary)
    return f"{column} IN ({values})"


_LANGUAGE_CHECK = "language ~ '^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$'"
_SHA256_CHECK = "char_length({column}) = 64 AND {column} ~ '^[0-9a-f]{{64}}$'"
_VERSION_RANGE = "BETWEEN 0 AND 9007199254740991"


class TranslationProposal(Base):
    """One pending aggregate for a stable translation key and language."""

    __tablename__ = "translation_proposals"
    __table_args__ = (
        CheckConstraint(_LANGUAGE_CHECK, name="language_normalized"),
        CheckConstraint(f"version {_VERSION_RANGE}", name="version_range"),
        CheckConstraint(
            _enum_check("state", ReviewState),
            name="state_value",
        ),
        CheckConstraint(
            "NOT reconciliation_required OR state = 'draft'",
            name="reconciliation_requires_draft",
        ),
        UniqueConstraint(
            "translation_key_id",
            "language",
            name="uq_translation_proposals_key_language",
        ),
        UniqueConstraint(
            "id",
            "translation_key_id",
            "language",
            name="uq_translation_proposals_owned_identity",
        ),
        ForeignKeyConstraint(
            ["translation_key_id", "scope_id"],
            ["translation_keys.id", "translation_keys.scope_id"],
            name="fk_translation_proposals_owned_key",
            ondelete="CASCADE",
        ),
        Index(
            "ix_translation_proposals_scope_language_state",
            "scope_id",
            "language",
            "state",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    scope_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    translation_key_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft"
    )
    reconciliation_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    values: Mapped[list[TranslationProposalValue]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranslationProposalValue.id",
    )
    activities: Mapped[list[ReviewActivity]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ReviewActivity.created_at, ReviewActivity.id",
    )


class TranslationProposalValue(Base):
    """A proposed selector value and the exact imported basis it was edited from."""

    __tablename__ = "translation_proposal_values"
    __table_args__ = (
        CheckConstraint(_LANGUAGE_CHECK, name="language_normalized"),
        CheckConstraint("selector_version = 1", name="selector_version_value"),
        CheckConstraint(
            _SHA256_CHECK.format(column="selector_digest"),
            name="selector_digest_sha256",
        ),
        CheckConstraint(
            "basis_revision_number >= 0",
            name="basis_revision_non_negative",
        ),
        CheckConstraint(
            _SHA256_CHECK.format(column="basis_digest"),
            name="basis_digest_sha256",
        ),
        CheckConstraint(
            "char_length(proposed_text) <= 1048576",
            name="proposed_text_length",
        ),
        CheckConstraint(
            "grapheme_count BETWEEN 0 AND 1048576",
            name="grapheme_count_range",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "translation_key_id", "language"],
            [
                "translation_proposals.id",
                "translation_proposals.translation_key_id",
                "translation_proposals.language",
            ],
            name="fk_translation_proposal_values_owned_proposal",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["translation_value_id", "translation_key_id"],
            ["translation_values.id", "translation_values.translation_key_id"],
            name="fk_translation_proposal_values_imported_value",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "proposal_id",
            "selector_version",
            "selector_digest",
            name="uq_translation_proposal_values_proposal_selector",
        ),
        Index(
            "ix_translation_proposal_values_imported_value",
            "translation_value_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    proposal_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    translation_key_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    translation_value_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    selector_version: Mapped[int] = mapped_column(Integer, nullable=False)
    selector_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    basis_revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    basis_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_text: Mapped[str] = mapped_column(Text, nullable=False)
    grapheme_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    proposal: Mapped[TranslationProposal] = relationship(back_populates="values")


class TranslationComment(Base):
    """Stable comment head attached to one key-language discussion."""

    __tablename__ = "translation_comments"
    __table_args__ = (
        CheckConstraint(_LANGUAGE_CHECK, name="language_normalized"),
        CheckConstraint(
            f"current_version {_VERSION_RANGE} AND current_version > 0",
            name="current_version_range",
        ),
        CheckConstraint(
            "(deleted_at IS NULL AND deleted_by IS NULL) OR "
            "(deleted_at IS NOT NULL AND deleted_by IS NOT NULL)",
            name="deletion_metadata_consistent",
        ),
        ForeignKeyConstraint(
            ["translation_key_id", "scope_id"],
            ["translation_keys.id", "translation_keys.scope_id"],
            name="fk_translation_comments_owned_key",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "id",
            "translation_key_id",
            "language",
            name="uq_translation_comments_owned_identity",
        ),
        Index(
            "ix_translation_comments_key_language_created",
            "translation_key_id",
            "language",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    scope_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    translation_key_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    author_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    versions: Mapped[list[TranslationCommentVersion]] = relationship(
        back_populates="comment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranslationCommentVersion.version_number",
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="originating_comment",
        passive_deletes=True,
        order_by="Notification.created_at, Notification.id",
    )


class TranslationCommentVersion(Base):
    """Immutable plain-text body revision for one stable comment."""

    __tablename__ = "translation_comment_versions"
    __table_args__ = (
        CheckConstraint(
            f"version_number {_VERSION_RANGE} AND version_number > 0",
            name="version_number_range",
        ),
        CheckConstraint(
            "char_length(body) BETWEEN 1 AND 65536 AND body ~ '[^[:space:]]'",
            name="body_nonblank_length",
        ),
        ForeignKeyConstraint(
            ["comment_id", "translation_key_id", "language"],
            [
                "translation_comments.id",
                "translation_comments.translation_key_id",
                "translation_comments.language",
            ],
            name="fk_translation_comment_versions_owned_comment",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "comment_id",
            "version_number",
            name="uq_translation_comment_versions_comment_number",
        ),
        UniqueConstraint(
            "id",
            "comment_id",
            name="uq_translation_comment_versions_owned_identity",
        ),
        Index(
            "ix_translation_comment_versions_comment_created",
            "comment_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    comment_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    translation_key_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    comment: Mapped[TranslationComment] = relationship(back_populates="versions")
    mentions: Mapped[list[TranslationCommentMention]] = relationship(
        back_populates="comment_version",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranslationCommentMention.start_utf16, TranslationCommentMention.id",
    )


class TranslationCommentMention(Base):
    """Immutable selected-user mention at browser-native UTF-16 offsets."""

    __tablename__ = "translation_comment_mentions"
    __table_args__ = (
        CheckConstraint(
            "start_utf16 >= 0 AND end_utf16 > start_utf16 AND end_utf16 <= 131072",
            name="utf16_range",
        ),
        CheckConstraint(
            "char_length(display_text) BETWEEN 2 AND 201",
            name="display_text_length",
        ),
        ForeignKeyConstraint(
            ["comment_version_id"],
            ["translation_comment_versions.id"],
            name="fk_translation_comment_mentions_version",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "comment_version_id",
            "start_utf16",
            "end_utf16",
            name="uq_translation_comment_mentions_version_range",
        ),
        Index(
            "ix_translation_comment_mentions_user",
            "mentioned_user_id",
            "comment_version_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    comment_version_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    mentioned_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_utf16: Mapped[int] = mapped_column(Integer, nullable=False)
    end_utf16: Mapped[int] = mapped_column(Integer, nullable=False)
    display_text: Mapped[str] = mapped_column(String(201), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    comment_version: Mapped[TranslationCommentVersion] = relationship(back_populates="mentions")


class ReviewActivity(Base):
    """Append-only proposal value or state-change evidence."""

    __tablename__ = "review_activities"
    __table_args__ = (
        CheckConstraint(_LANGUAGE_CHECK, name="language_normalized"),
        CheckConstraint(
            _enum_check("kind", ReviewActivityKind),
            name="kind_value",
        ),
        CheckConstraint(
            f"proposal_version {_VERSION_RANGE}",
            name="proposal_version_range",
        ),
        CheckConstraint(
            "from_state IS NULL OR from_state IN ('draft', 'approved', 'rejected')",
            name="from_state_value",
        ),
        CheckConstraint(
            "to_state IS NULL OR to_state IN ('draft', 'approved', 'rejected')",
            name="to_state_value",
        ),
        CheckConstraint(
            "reason IS NULL OR char_length(reason) <= 4096",
            name="reason_length",
        ),
        CheckConstraint(
            "before_values IS NULL OR jsonb_typeof(before_values) = 'array'",
            name="before_values_array",
        ),
        CheckConstraint(
            "after_values IS NULL OR jsonb_typeof(after_values) = 'array'",
            name="after_values_array",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "translation_key_id", "language"],
            [
                "translation_proposals.id",
                "translation_proposals.translation_key_id",
                "translation_proposals.language",
            ],
            name="fk_review_activities_owned_proposal",
            ondelete="CASCADE",
        ),
        Index(
            "ix_review_activities_proposal_created",
            "proposal_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    proposal_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    translation_key_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    before_values: Mapped[list[object] | None] = mapped_column(JSONB, nullable=True)
    after_values: Mapped[list[object] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("translation_comments.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    proposal: Mapped[TranslationProposal] = relationship(back_populates="activities")


class Notification(Base):
    """Recipient-owned durable mention notification."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            _enum_check("kind", NotificationKind),
            name="kind_value",
        ),
        CheckConstraint(
            "recipient_user_id <> actor_user_id",
            name="actor_is_not_recipient",
        ),
        UniqueConstraint(
            "recipient_user_id",
            "originating_comment_id",
            "kind",
            name="uq_notifications_recipient_comment_kind",
        ),
        Index(
            "ix_notifications_recipient_unread_created",
            "recipient_user_id",
            "created_at",
            "id",
            postgresql_where=text("read_at IS NULL"),
        ),
        Index(
            "ix_notifications_recipient_created",
            "recipient_user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    recipient_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_notifications_recipient",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    originating_comment_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "translation_comments.id",
            name="fk_notifications_originating_comment",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(
        String(24), nullable=False, default="mention", server_default="mention"
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    originating_comment: Mapped[TranslationComment] = relationship(back_populates="notifications")
