"""Provider-independent roles and the many-to-many authority mapping."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verboflex.db.base import Base

if TYPE_CHECKING:
    from verboflex.models.user import User

ROLE_NAMES = (
    "admin",
    "product_manager_reviewer",
    "translator",
    "viewer",
)

user_roles_table = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)


class Role(Base):
    """A stable internal authorization role."""

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    users: Mapped[list[User]] = relationship(
        secondary=user_roles_table,
        back_populates="roles",
        lazy="selectin",
    )
