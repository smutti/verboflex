"""Worker-owned diagnostic records, never canonical translation identities."""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class DuplicateReportRow(Base):
    __tablename__ = "duplicate_reports"
    __table_args__ = (
        CheckConstraint("(preview_job_id IS NULL) <> (execution_id IS NULL)", name="exact_owner"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    preview_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("preview_jobs.id", ondelete="CASCADE"), unique=True
    )
    execution_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("import_executions.id", ondelete="CASCADE"), unique=True
    )
    complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    issue_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    group_count: Mapped[int] = mapped_column(Integer, nullable=False)
    repeated_occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
    sources: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False)


class DuplicateGroupRow(Base):
    __tablename__ = "duplicate_groups"
    __table_args__ = (UniqueConstraint("report_id", "identity_digest"),)

    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("duplicate_reports.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    repository_side: Mapped[str] = mapped_column(String(16), nullable=False)
    layout_identity: Mapped[str] = mapped_column(String(4096), nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    key_preview: Mapped[str] = mapped_column(String(512), nullable=False)
    key_length: Mapped[int] = mapped_column(Integer, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)


class DuplicateOccurrenceRow(Base):
    __tablename__ = "duplicate_occurrences"

    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("duplicate_reports.id", ondelete="CASCADE"), primary_key=True
    )
    group_position: Mapped[int] = mapped_column(Integer, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(4096), nullable=False)
    resource_position: Mapped[int] = mapped_column(Integer, nullable=False)
