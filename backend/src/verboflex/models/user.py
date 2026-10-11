"""Internal corporate-email identity model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verboflex.db.base import Base
from verboflex.models.role import user_roles_table

if TYPE_CHECKING:
    from verboflex.models.auth_session import AuthSession
    from verboflex.models.role import Role


class User(Base):
    """An internal account whose authority remains identity-provider independent."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            r"email = lower(btrim(email, E' \t\n\r\f\v'))",
            name="email_normalized",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles_table,
        back_populates="users",
        lazy="selectin",
        order_by="Role.name",
    )
    auth_sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
