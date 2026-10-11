"""Stable product identity and immutable published configuration revisions."""

from __future__ import annotations

from datetime import datetime
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
    event,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.engine import Connection
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
        ForeignKeyConstraint(
            ["id", "active_revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            name="fk_products_active_owned_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["deleted_by"],
            ["users.id"],
            name="fk_products_deleted_by_users",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(deleted_at IS NULL) = (deleted_by IS NULL)",
            name="deleted_identity_complete",
        ),
        CheckConstraint(
            "deleted_at IS NULL OR NOT is_active",
            name="deleted_inactive",
        ),
        Index(
            "uq_products_live_name_key",
            "name_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        ForeignKeyConstraint(
            ["id", "candidate_revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            name="fk_products_candidate_owned_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_key: Mapped[str] = mapped_column(String(360), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    active_revision_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    candidate_revision_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=True)

    revisions: Mapped[list[ProductRevision]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        foreign_keys="ProductRevision.product_id",
        passive_deletes=True,
    )
    active_revision: Mapped[ProductRevision | None] = relationship(
        primaryjoin="and_(Product.id == ProductRevision.product_id, "
        "Product.active_revision_id == ProductRevision.id)",
        foreign_keys="[Product.id, Product.active_revision_id]",
        viewonly=True,
    )
    candidate_revision: Mapped[ProductRevision | None] = relationship(
        primaryjoin="and_(Product.id == ProductRevision.product_id, "
        "Product.candidate_revision_id == ProductRevision.id)",
        foreign_keys="[Product.id, Product.candidate_revision_id]",
        viewonly=True,
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
        CheckConstraint(
            "char_length(display_name) BETWEEN 1 AND 120",
            name="display_name_length",
        ),
        CheckConstraint(
            "char_length(name_key) BETWEEN 1 AND 360",
            name="name_key_length",
        ),
        UniqueConstraint(
            "product_id",
            "id",
            name="uq_product_revisions_product_id_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_key: Mapped[str] = mapped_column(String(360), nullable=False)
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


@event.listens_for(ProductRevision, "before_insert")
def _snapshot_missing_revision_identity(
    _mapper: object,
    connection: Connection,
    target: ProductRevision,
) -> None:
    """Keep established ORM construction paths valid until callers pass snapshots."""
    if target.display_name is not None and target.name_key is not None:
        return
    display_name, name_key = connection.execute(
        select(Product.display_name, Product.name_key).where(Product.id == target.product_id)
    ).one()
    if target.display_name is None:
        target.display_name = display_name
    if target.name_key is None:
        target.name_key = name_key
