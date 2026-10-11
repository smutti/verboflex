"""Pending structural additions are independent of the imported dataset."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class AuthoringRequest(Base):
    __tablename__ = "translation_authoring_requests"
    __table_args__ = (
        CheckConstraint("state IN ('draft','approved','rejected')", name="state"),
        CheckConstraint("version BETWEEN 1 AND 9007199254740991", name="version"),
        CheckConstraint("char_length(raw_key) BETWEEN 1 AND 4096", name="key_bound"),
        CheckConstraint(
            "jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 1048576",
            name="payload_bound",
        ),
        Index("uq_authoring_identity", "scope_id", "identity_digest", unique=True),
        Index("ix_authoring_scope_page", "scope_id", "id"),
        Index("ix_authoring_parent_key_id", "parent_key_id"),
        Index("ix_authoring_created_by", "created_by"),
        Index("ix_authoring_updated_by", "updated_by"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    scope_id: Mapped[UUID] = mapped_column(
        ForeignKey("localization_scopes.id", ondelete="CASCADE", name="fk_authoring_scope")
    )
    parent_key_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("translation_keys.id", ondelete="CASCADE", name="fk_authoring_parent")
    )
    raw_key: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(64))
    identity_digest: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    state: Mapped[str] = mapped_column(String(16), default="draft")
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_authoring_creator")
    )
    updated_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_authoring_editor")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
