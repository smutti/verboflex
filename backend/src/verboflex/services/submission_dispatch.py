"""Bounded durable delivery of accepted change-set identities."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.models.submission import ChangeSet, ChangeSetEvent
from verboflex.services.submission_jobs import _clear_owner, _lock_group
from verboflex.services.submission_recovery import effect_summary

REDELIVERY_DELAY = timedelta(seconds=30)


def dispatch_pending_submissions(
    factory: sessionmaker[Session],
    *,
    enqueue_send: Callable[[UUID], None],
    enqueue_reconcile: Callable[[UUID], None],
    limit: int = 50,
) -> int:
    """Persist delivery intent before broker I/O; a consumer clears the outbox bit."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid dispatch limit")
    now = datetime.now(UTC)
    due = or_(
        ChangeSet.last_dispatched_at.is_(None),
        ChangeSet.last_dispatched_at <= now - REDELIVERY_DELAY,
    )
    with factory() as session:
        identities = list(
            session.scalars(
                select(ChangeSet.id)
                .where(
                    ChangeSet.claims_released_at.is_(None),
                    or_(
                        and_(
                            ChangeSet.dispatch_pending.is_(True),
                            due,
                            ChangeSet.status.in_(("queued", "reconciling")),
                        ),
                        and_(
                            ChangeSet.status == "running",
                            ChangeSet.owner_id.is_not(None),
                            ChangeSet.lease_expires_at <= now,
                        ),
                    ),
                )
                .order_by(ChangeSet.created_at, ChangeSet.id)
                .limit(limit)
            )
        )
    dispatched = 0
    for identity in identities:
        with factory.begin() as session:
            # Never lock a group before its product; intake and recovery use this order.
            row = _lock_group(session, identity)
            if row is None or row.claims_released_at is not None:
                continue
            expired = (
                row.status == "running"
                and row.owner_id is not None
                and row.lease_expires_at is not None
                and row.lease_expires_at <= now
            )
            if expired:
                effects = effect_summary(session, row)
                if not effects.bounded or "conflict" in (
                    effects.branch,
                    effects.commit,
                    effects.pull_request,
                ):
                    row.status, row.error_code = "needs_attention", "provider_conflict"
                    _clear_owner(row)
                    continue
                read_only_owner = (
                    session.scalar(
                        select(ChangeSetEvent.id)
                        .where(
                            ChangeSetEvent.change_set_id == row.id,
                            ChangeSetEvent.attempt == row.attempt,
                            ChangeSetEvent.execution_fence == row.execution_fence,
                            ChangeSetEvent.event_kind == "reauthorization",
                            ChangeSetEvent.receipt["action"].as_string()
                            == "reconciliation_started",
                        )
                        .limit(1)
                    )
                    is not None
                )
                retry_intent = session.scalar(
                    select(ChangeSetEvent)
                    .where(
                        ChangeSetEvent.change_set_id == row.id,
                        ChangeSetEvent.attempt == row.attempt,
                        ChangeSetEvent.execution_fence == row.execution_fence,
                        ChangeSetEvent.event_kind == "reauthorization",
                        ChangeSetEvent.step == "authority",
                        ChangeSetEvent.outcome == "intent",
                        ChangeSetEvent.receipt["action"]
                        .as_string()
                        .in_(("retry", "resume_explicit_retry")),
                    )
                    .limit(1)
                )
                row.attempt += 1
                row.execution_fence += 1
                _clear_owner(row)
                if read_only_owner and not effects.unresolved and row.pr_id is None:
                    # A crash after adopting a read-only receipt must still require Retry.
                    row.status, row.error_code = "blocked", "recovered_review_required"
                    row.finished_at = now
                    continue
                row.status = "reconciling" if effects.unresolved or row.pr_id else "queued"
                row.error_code, row.dispatch_pending = None, True
                if retry_intent is not None and row.status == "queued":
                    # Carry only an already explicit retry, never invent renewal authority.
                    session.add(
                        ChangeSetEvent(
                            change_set_id=row.id,
                            attempt=row.attempt,
                            execution_fence=row.execution_fence,
                            proof_sequence=row.current_proof_sequence,
                            event_kind="reauthorization",
                            step="authority",
                            outcome="intent",
                            request_digest=retry_intent.request_digest,
                            receipt={"action": "resume_explicit_retry"},
                            provider_status=None,
                        )
                    )
            elif (
                not row.dispatch_pending
                or row.status not in {"queued", "reconciling"}
                or row.owner_id is not None
                or (
                    row.last_dispatched_at is not None
                    and row.last_dispatched_at > now - REDELIVERY_DELAY
                )
            ):
                continue
            reconcile = row.status == "reconciling"
            row.last_dispatched_at = now
            row.dispatch_count += 1
        # No transaction crosses queue I/O. The persisted bit remains set even on loss.
        try:
            (enqueue_reconcile if reconcile else enqueue_send)(identity)
        except Exception:
            continue
        dispatched += 1
    return dispatched
