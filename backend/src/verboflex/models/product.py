"""Stable product identity and immutable published configuration revisions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verboflex.db.base import Base


class Product(Base):
    """One UUID identity with explicit active and candidate revision pointers."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "char_length(display_name) BETWEEN 1 AND 120",
            name="display_name_length",
        ),
        CheckConstraint(
            "char_length(name_key) BETWEEN 1 AND 360",
            name="name_key_length",
        ),
        CheckConstraint(
            "active_revision_id IS NULL OR candidate_revision_id IS NULL "
            "OR active_revision_id <> candidate_revision_id",
            name="distinct_revision_pointers",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_key: Mapped[str] = mapped_column(String(360), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    active_revision_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "product_revisions.id",
            name="fk_products_active_revision_id_product_revisions",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        nullable=True,
    )
    candidate_revision_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "product_revisions.id",
            name="fk_products_candidate_revision_id_product_revisions",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        nullable=True,
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

    revisions: Mapped[list[ProductRevision]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        foreign_keys="ProductRevision.product_id",
        passive_deletes=True,
    )
    active_revision: Mapped[ProductRevision | None] = relationship(
        foreign_keys=[active_revision_id],
        post_update=True,
    )
    candidate_revision: Mapped[ProductRevision | None] = relationship(
        foreign_keys=[candidate_revision_id],
        post_update=True,
    )


class ProductRevision(Base):
    """One configuration graph root; published rows become database immutable."""

    __tablename__ = "product_revisions"
    __table_args__ = (
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint(
            "(is_published AND published_at IS NOT NULL) "
            "OR (NOT is_published AND published_at IS NULL)",
            name="publication_timestamp_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    product: Mapped[Product] = relationship(
        back_populates="revisions",
        foreign_keys=[product_id],
    )
