"""Versioned explicit maximum-length rules for canonical translation keys."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base

_LANGUAGE_CHECK = "language ~ '^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$'"


class TranslationConstraint(Base):
    """One explicit language rule under a stable translation-key identity."""

    __tablename__ = "translation_constraints"
    __table_args__ = (
        CheckConstraint(_LANGUAGE_CHECK, name="language_normalized"),
        CheckConstraint(
            "max_chars BETWEEN 0 AND 1048576",
            name="max_chars_bound",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint(
            "translation_key_id",
            "language",
            name="uq_translation_constraints_key_language",
        ),
        ForeignKeyConstraint(
            ["translation_key_id", "scope_id"],
            ["translation_keys.id", "translation_keys.scope_id"],
            name="fk_translation_constraints_owned_key",
            ondelete="CASCADE",
        ),
        Index(
            "ix_translation_constraints_scope_language",
            "scope_id",
            "language",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    scope_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    translation_key_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    max_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
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
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
