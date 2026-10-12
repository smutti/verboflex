"""Product-scoped authority and immutable team receipts."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base

PRODUCT_ROLES = ("viewer", "translator", "product_manager_reviewer", "product_owner")


class ProductMember(Base):
    __tablename__ = "product_members"
    __table_args__ = (
        CheckConstraint(
            "role IN ('viewer','translator','product_manager_reviewer','product_owner')",
            name="role",
        ),
        Index("ix_product_members_user", "user_id", "product_id"),
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    version: Mapped[UUID] = mapped_column(default=uuid4)


class ProductTeamEvent(Base):
    """Snapshot IDs survive account/product removal; never store passwords."""

    __tablename__ = "product_team_events"
    __table_args__ = (Index("ix_product_team_events_product", "product_id", "occurred_at"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column()
    product_id: Mapped[UUID] = mapped_column()
    subject_id: Mapped[UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(32))
    previous_role: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[str | None] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
