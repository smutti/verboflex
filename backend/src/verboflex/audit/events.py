"""Bounded structured audit events without durable audit-history ownership."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

AuditAction = Literal[
    "bitbucket.connected",
    "bitbucket.refreshed",
    "bitbucket.reauthorization_required",
    "bitbucket.revoked",
]


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One secret-free lifecycle fact safe for structured logging."""

    action: AuditAction
    actor_id: UUID
    from_generation: int
    to_generation: int
    occurred_at: datetime


AuditEventEmitter = Callable[[AuditEvent], None]
_LOGGER = logging.getLogger("verboflex.audit")


def emit_audit_event(event: AuditEvent) -> None:
    """Emit only bounded identifiers and generation metadata."""
    _LOGGER.info(
        "audit action=%s actor_id=%s from_generation=%d to_generation=%d occurred_at=%s",
        event.action,
        event.actor_id,
        event.from_generation,
        event.to_generation,
        event.occurred_at.isoformat(),
    )


def new_audit_event(
    *,
    action: AuditAction,
    actor_id: UUID,
    from_generation: int,
    to_generation: int,
    occurred_at: datetime | None = None,
) -> AuditEvent:
    """Build one UTC lifecycle event without provider material."""
    return AuditEvent(
        action=action,
        actor_id=actor_id,
        from_generation=from_generation,
        to_generation=to_generation,
        occurred_at=occurred_at or datetime.now(UTC),
    )
