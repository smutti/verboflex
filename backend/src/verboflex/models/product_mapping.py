"""Revision-owned repository mappings and exact branch target sets."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verboflex.db.base import Base


class ProductRepositoryMapping(Base):
    """One mapping identity owned exclusively by one configuration revision."""

    __tablename__ = "product_repository_mappings"
    __table_args__ = (
        CheckConstraint(
            "topology IN ('direct', 'separate')",
            name="topology_value",
        ),
        CheckConstraint(
            "char_length(identity_key) BETWEEN 1 AND 1200",
            name="identity_key_length",
        ),
        CheckConstraint(
            "(selected_layout_candidate_id IS NULL AND selected_layout_version IS NULL) OR "
            "(selected_layout_candidate_id IS NOT NULL AND selected_layout_version > 0)",
            name="selected_layout_state",
        ),
        CheckConstraint(
            "(confirmed_preview_job_id IS NULL AND confirmed_preview_digest IS NULL "
            "AND preview_confirmed_by IS NULL AND preview_confirmed_at IS NULL) OR "
            "(confirmed_preview_job_id IS NOT NULL "
            "AND char_length(confirmed_preview_digest) = 64 "
            "AND confirmed_preview_digest ~ '^[0-9a-f]{64}$' "
            "AND preview_confirmed_by IS NOT NULL AND preview_confirmed_at IS NOT NULL)",
            name="preview_confirmation_state",
        ),
        UniqueConstraint(
            "revision_id",
            "identity_key",
            name="uq_product_repository_mappings_revision_identity",
        ),
        UniqueConstraint(
            "confirmed_preview_job_id",
            name="uq_product_repository_mappings_confirmed_preview_job",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    revision_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("product_revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topology: Mapped[str] = mapped_column(String(16), nullable=False)
    identity_key: Mapped[str] = mapped_column(String(1200), nullable=False)
    selected_layout_candidate_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    selected_layout_version: Mapped[int | None] = mapped_column(nullable=True)
    confirmed_preview_job_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("preview_jobs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    confirmed_preview_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    preview_confirmed_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    preview_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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

    sides: Mapped[list[ProductMappingRepositorySide]] = relationship(
        back_populates="mapping",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProductMappingRepositorySide.role",
    )
    allowed_targets: Mapped[list[ProductMappingAllowedTarget]] = relationship(
        back_populates="mapping",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProductMappingAllowedTarget.branch",
    )


class ProductMappingRepositorySide(Base):
    """One explicit Direct, Keys, or Translations repository side."""

    __tablename__ = "product_mapping_repository_sides"
    __table_args__ = (
        CheckConstraint(
            "role IN ('direct', 'keys', 'translations')",
            name="role_value",
        ),
        CheckConstraint(
            "char_length(source_branch) BETWEEN 1 AND 255",
            name="source_branch_length",
        ),
    )

    mapping_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("product_repository_mappings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(16), primary_key=True)
    repository_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_branch: Mapped[str] = mapped_column(String(255), nullable=False)

    mapping: Mapped[ProductRepositoryMapping] = relationship(back_populates="sides")


class ProductMappingAllowedTarget(Base):
    """One exact target branch, with exactly one service-selected default."""

    __tablename__ = "product_mapping_allowed_targets"
    __table_args__ = (
        CheckConstraint(
            "char_length(branch) BETWEEN 1 AND 255",
            name="branch_length",
        ),
        Index(
            "uq_product_mapping_allowed_targets_one_default",
            "mapping_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    mapping_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("product_repository_mappings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    branch: Mapped[str] = mapped_column(String(255), primary_key=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    mapping: Mapped[ProductRepositoryMapping] = relationship(back_populates="allowed_targets")
