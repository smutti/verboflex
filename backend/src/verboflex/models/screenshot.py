"""Short-lived immutable capture receipts, expiring independently of source deletion."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class ScreenshotJob(Base):
    __tablename__ = "screenshot_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued','rendering','succeeded','failed','cancelled','expired')",
            name="state",
        ),
        CheckConstraint("image IS NULL OR octet_length(image) <= 8388608", name="image_bound"),
        CheckConstraint("octet_length(inputs::text) <= 8388608", name="input_bound"),
        Index("ix_screenshot_actor_created", "actor_id", "created_at"),
        Index("ix_screenshot_group_created", "group_id", "created_at"),
        Index("ix_screenshot_state_updated", "state", "updated_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    actor_id: Mapped[UUID] = mapped_column()
    product_id: Mapped[UUID] = mapped_column()
    group_id: Mapped[UUID] = mapped_column()
    scope_id: Mapped[UUID] = mapped_column()
    execution_id: Mapped[UUID] = mapped_column()
    membership_stamp: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(16), default="queued")
    request: Mapped[dict[str, object]] = mapped_column(JSONB)
    inputs: Mapped[dict[str, object]] = mapped_column(JSONB)
    input_digest: Mapped[str] = mapped_column(String(64))
    image: Mapped[bytes | None] = mapped_column(LargeBinary)
    image_digest: Mapped[str | None] = mapped_column(String(64))
    location: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
