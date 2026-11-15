"""Durable, immutable project-wide draft approval requests."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class AuthoringApproval(Base):
    __tablename__ = "authoring_approvals"
    __table_args__ = (
        CheckConstraint("state IN ('queued','succeeded','failed')", name="state"),
        CheckConstraint(
            "jsonb_typeof(selection) = 'array' "
            "AND jsonb_array_length(selection) BETWEEN 1 AND 5000 "
            "AND octet_length(selection::text) <= 1048576",
            name="selection_bound",
        ),
        Index("ix_authoring_approvals_product", "product_id", "created_at"),
        Index(
            "uq_authoring_approvals_pending",
            "product_id",
            unique=True,
            postgresql_where=text("state = 'queued'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    membership: Mapped[str] = mapped_column(String(80))
    fingerprint: Mapped[str] = mapped_column(String(64))
    selection: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(16), default="queued")
    error: Mapped[str | None] = mapped_column(String(1024))
    branch_job_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
