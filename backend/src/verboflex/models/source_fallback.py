"""Explicit product-owned source-language decisions, independent of Git imports."""

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class SourceFallbackPolicy(Base):
    __tablename__ = "source_fallback_policies"
    __table_args__ = (CheckConstraint("version >= 1", name="version_positive"),)

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    language: Mapped[str | None] = mapped_column(String(64))


class SourceFallbackText(Base):
    __tablename__ = "source_fallback_texts"

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_fallback_policies.product_id", ondelete="CASCADE"), primary_key=True
    )
    source_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
