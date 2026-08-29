"""Durable preview job attempts and complete pre-detector identity."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class PreviewJob(Base):
    """One immutable input identity and one bounded execution attempt."""

    __tablename__ = "preview_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', 'timed_out')",
            name="state_value",
        ),
        CheckConstraint("attempt > 0", name="positive_attempt"),
        CheckConstraint(
            "candidate_revision_version > 0",
            name="positive_candidate_revision_version",
        ),
        CheckConstraint("connection_generation >= 0", name="connection_generation_non_negative"),
        CheckConstraint(
            "char_length(input_digest) = 64 AND input_digest ~ '^[0-9a-f]{64}$'",
            name="input_digest_sha256",
        ),
        CheckConstraint(
            "char_length(detector_version) BETWEEN 1 AND 64",
            name="detector_version_length",
        ),
        CheckConstraint(
            "char_length(layout_identity) BETWEEN 1 AND 128",
            name="layout_identity_length",
        ),
        CheckConstraint(
            "(state = 'queued' AND started_at IS NULL AND finished_at IS NULL "
            "AND result IS NULL AND error_code IS NULL) OR "
            "(state = 'running' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND result IS NULL AND error_code IS NULL) OR "
            "(state = 'succeeded' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND result IS NOT NULL AND error_code IS NULL) OR "
            "(state IN ('failed', 'timed_out') AND finished_at IS NOT NULL "
            "AND result IS NULL AND error_code IS NOT NULL)",
            name="state_payload",
        ),
        UniqueConstraint(
            "input_digest",
            "attempt",
            name="uq_preview_jobs_digest_attempt",
        ),
        ForeignKeyConstraint(
            ["product_id", "candidate_revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            name="fk_preview_jobs_owned_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["candidate_revision_id", "mapping_id"],
            ["product_repository_mappings.revision_id", "product_repository_mappings.id"],
            name="fk_preview_jobs_owned_mapping",
            ondelete="CASCADE",
        ),
        Index(
            "ix_preview_jobs_mapping_digest_attempt",
            "mapping_id",
            "input_digest",
            "attempt",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    product_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    candidate_revision_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    candidate_revision_version: Mapped[int] = mapped_column(Integer, nullable=False)
    mapping_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    topology: Mapped[str] = mapped_column(String(16), nullable=False)
    connection_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    detector_version: Mapped[str] = mapped_column(String(64), nullable=False)
    layout_identity: Mapped[str] = mapped_column(String(128), nullable=False)
    repository_sides: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
