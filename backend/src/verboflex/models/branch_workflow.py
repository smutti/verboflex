"""Persistent approval commits and explicitly requested pull requests."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class BranchWorkflow(Base):
    __tablename__ = "branch_workflows"
    __table_args__ = (
        UniqueConstraint("mapping_id"),
        UniqueConstraint("repository_id", "work_branch"),
        CheckConstraint("work_branch <> target_branch", name="distinct_branches"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    mapping_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_repository_mappings.id", ondelete="RESTRICT")
    )
    repository_id: Mapped[UUID] = mapped_column(ForeignKey("repositories.id", ondelete="RESTRICT"))
    work_branch: Mapped[str] = mapped_column(String(255))
    target_branch: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BranchJob(Base):
    __tablename__ = "branch_jobs"
    __table_args__ = (
        UniqueConstraint("activity_id"),
        CheckConstraint("kind IN ('commit','pull_request')", name="kind"),
        CheckConstraint(
            "state IN ('queued','running','sending','committed','open',"
            "'merged','declined','blocked')",
            name="state",
        ),
        CheckConstraint(
            "authority IS NULL OR octet_length(authority) <= 134217728", name="authority_bound"
        ),
        CheckConstraint(
            "intent IS NULL OR octet_length(intent::text) <= 134217728", name="intent_bound"
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    sequence: Mapped[int] = mapped_column(Integer, Identity(), unique=True)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("branch_workflows.id", ondelete="RESTRICT"), index=True
    )
    activity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    membership: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), default="queued")
    label: Mapped[str] = mapped_column(String(1024))
    authority: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    intent: Mapped[dict[str, object] | None] = mapped_column(JSONB, deferred=True)
    commit_hash: Mapped[str | None] = mapped_column(String(40))
    pr_id: Mapped[int | None] = mapped_column(Integer)
    pr_url: Mapped[str | None] = mapped_column(String(4096))
    error_code: Mapped[str | None] = mapped_column(String(64))
    owner: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BranchFile(Base):
    __tablename__ = "branch_files"
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("branch_workflows.id", ondelete="RESTRICT"), primary_key=True
    )
    path_digest: Mapped[str] = mapped_column(
        String(32), Computed("md5(path)", persisted=True), primary_key=True
    )
    path: Mapped[str] = mapped_column(String(4096))
    baseline_sha256: Mapped[str] = mapped_column(String(64))
    content_sha256: Mapped[str] = mapped_column(String(64))
    edits: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
