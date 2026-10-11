"""Write bounded audit metadata inside the caller's mutation transaction."""

from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from verboflex.models.audit import AUDIT_ACTIONS, AuditEntry

# A fixed UUID identifies the installation-wide Bitbucket configuration singleton.
BITBUCKET_AUDIT_ENTITY = UUID("00000000-0000-0000-0000-000000000001")


def record_audit(
    session: Session,
    *,
    actor_id: UUID | None,
    action: str,
    entity_id: UUID,
    system: bool = False,
) -> None:
    """Never commit, log bodies, or open a separate transaction.

    None denotes a privileged local operator, never an anonymous HTTP user.
    HTTP callers must pass the authenticated principal's UUID explicitly.
    """
    if not session.in_transaction():
        raise ValueError("audit requires an existing mutation transaction")
    if action not in AUDIT_ACTIONS or not isinstance(entity_id, UUID):
        raise ValueError("invalid audit identity")
    if actor_id is not None and not isinstance(actor_id, UUID):
        raise ValueError("invalid audit actor")
    if system and actor_id is not None:
        raise ValueError("system audit cannot impersonate a user")
    actor_kind: Literal["user", "operator", "system"] = (
        "system" if system else "operator" if actor_id is None else "user"
    )
    session.add(
        AuditEntry(
            actor_id=actor_id,
            actor_kind=actor_kind,
            action=action,
            entity_id=entity_id,
        )
    )
