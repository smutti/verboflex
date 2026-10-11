"""Current project terminology, physically removed when deleted."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class GlossaryEntry(Base):
    __tablename__ = "glossary_entries"
    __table_args__ = (
        CheckConstraint("version BETWEEN 1 AND 9007199254740991", name="version"),
        CheckConstraint("char_length(source_term) BETWEEN 1 AND 256", name="source_bound"),
        CheckConstraint("char_length(target_term) BETWEEN 1 AND 256", name="target_bound"),
        Index("uq_glossary_identity", "product_id", "identity_digest", unique=True),
        Index("ix_glossary_pair", "product_id", "source_language", "target_language", "id"),
        Index("ix_glossary_creator", "created_by"),
        Index("ix_glossary_editor", "updated_by"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE", name="fk_glossary_product")
    )
    identity_digest: Mapped[str] = mapped_column(String(64))
    source_language: Mapped[str] = mapped_column(String(32))
    target_language: Mapped[str] = mapped_column(String(32))
    source_term: Mapped[str] = mapped_column(String(256))
    target_term: Mapped[str] = mapped_column(String(256))
    forbidden: Mapped[bool] = mapped_column(Boolean, default=False)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String(1000), default="")
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_glossary_creator")
    )
    updated_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_glossary_editor")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
