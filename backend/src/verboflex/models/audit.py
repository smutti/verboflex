"""Content-free mutation receipts, independent of removable domain records."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base

AUDIT_ACTIONS = (
    "branch.configured",
    "branch.approval_queued",
    "branch.pr_requested",
    "branch.retry_requested",
    "product.created",
    "product.updated",
    "product.published",
    "product.deactivated",
    "product.reactivated",
    "product.deleted",
    "mapping.created",
    "mapping.updated",
    "repository.registered",
    "workspace.updated",
    "user.created",
    "user.updated",
    "user.password_reset",
    "user.password_changed",
    "user.deactivated",
    "user.reactivated",
    "constraint.updated",
    "constraint.deleted",
    "preview.requested",
    "import.requested",
    "bitbucket.connected",
    "bitbucket.refreshed",
    "bitbucket.revoked",
    "authoring.saved",
    "authoring.approved",
    "authoring.rejected",
    "authoring.reopened",
    "authoring.deleted",
    "glossary.saved",
    "glossary.deleted",
)


class AuditEntry(Base):
    """Actor UUIDs are snapshots, not foreign keys that prevent data erasure.

    Entity type is the closed action prefix. No arbitrary metadata/body column is
    available. Privileged local CLI actions use an explicit operator identity.
    """

    __tablename__ = "audit_entries"
    __table_args__ = (
        CheckConstraint(
            "action IN (" + ", ".join(repr(value) for value in AUDIT_ACTIONS) + ")",
            name="known_action",
        ),
        CheckConstraint(
            "(actor_kind = 'user' AND actor_id IS NOT NULL) OR "
            "(actor_kind IN ('operator', 'system') AND actor_id IS NULL)",
            name="actor_identity",
        ),
        Index("ix_audit_entries_entity_time", "entity_id", "occurred_at", "id"),
        Index("ix_audit_entries_actor_time", "actor_id", "occurred_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=True)
    actor_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
    )
