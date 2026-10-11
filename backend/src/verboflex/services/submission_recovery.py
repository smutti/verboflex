"""Explicit recovery authorization and irreversible release of proven effects."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from sqlalchemy import Text, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from verboflex.integrations.bitbucket.writes import (
    BitbucketWriteAdapter,
    PullRequestIntent,
    PullRequestReceipt,
    WriteContext,
)
from verboflex.localization.writing.core import WritebackReason, WritebackRejected
from verboflex.models.submission import (
    ChangeSet,
    ChangeSetEvent,
    ChangeSetFile,
    ChangeSetProof,
    SubmissionBatch,
)
from verboflex.models.user import User
from verboflex.schemas.submissions import ChangeSetResponse
from verboflex.services.submission_codec import encode_prepared_writeback
from verboflex.services.submission_reviews import (
    REVIEW_ROLES,
    SubmissionReviewDenied,
    SubmissionReviewUnavailable,
    _product_actor,
)
from verboflex.services.submission_selection import SubmissionReadAdapter, check_target
from verboflex.services.submissions import (
    ChangeSetBundle,
    SubmissionConflict,
    change_set_response,
    enqueue_submission,
    load_change_set_bundle,
)
from verboflex.services.writeback import prepare_writeback, revalidate_writeback_authority

if TYPE_CHECKING:
    from verboflex.services.submission_jobs import AttemptIdentity

EffectState = Literal["never", "not_sent", "verified", "unknown", "conflict"]
MAX_INTENTS = 512
MAX_OBSERVATIONS = 2048
STEPS = ("branch", "commit", "pull_request")


@dataclass(frozen=True, slots=True)
class EffectSummary:
    branch: EffectState
    commit: EffectState
    pull_request: EffectState
    bounded: bool = True

    @property
    def unresolved(self) -> bool:
        return not self.bounded or any(
            value in {"unknown", "conflict"}
            for value in (self.branch, self.commit, self.pull_request)
        )


def effect_summary(session: Session, row: ChangeSet) -> EffectSummary:
    """Inspect bounded journal metadata; positive evidence survives a lost later read."""
    base = ChangeSetEvent.change_set_id == row.id
    counts: dict[str, int] = {
        kind: count
        for kind, count in session.execute(
            select(ChangeSetEvent.event_kind, func.count())
            .where(base, ChangeSetEvent.event_kind.in_(("send_intent", "observation")))
            .group_by(ChangeSetEvent.event_kind)
        ).all()
    }
    if (
        counts.get("send_intent", 0) > MAX_INTENTS
        or counts.get("observation", 0) > MAX_OBSERVATIONS
    ):
        return EffectSummary("unknown", "unknown", "unknown", False)
    # Receipt identity is projected to a bounded digest in PostgreSQL. PR lifecycle
    # and observed destination head may advance without changing PR identity.
    signature = func.encode(
        func.sha256(
            func.convert_to(
                func.jsonb_build_array(
                    ChangeSetEvent.receipt["id"],
                    ChangeSetEvent.receipt["repository_id"],
                    ChangeSetEvent.receipt["source_branch"],
                    ChangeSetEvent.receipt["source_commit"],
                    ChangeSetEvent.receipt["target_branch"],
                    ChangeSetEvent.receipt["name"],
                    ChangeSetEvent.receipt["commit_hash"],
                    ChangeSetEvent.receipt["parent"],
                    ChangeSetEvent.receipt["branch"],
                    ChangeSetEvent.receipt["manifest_digest"],
                ).cast(Text),
                "UTF8",
            )
        ),
        "hex",
    )
    events = session.execute(
        select(
            ChangeSetEvent.step,
            ChangeSetEvent.attempt,
            ChangeSetEvent.execution_fence,
            ChangeSetEvent.request_digest,
            ChangeSetEvent.event_kind,
            ChangeSetEvent.outcome,
            signature,
        )
        .where(base, ChangeSetEvent.event_kind.in_(("send_intent", "observation")))
        .limit(MAX_INTENTS + MAX_OBSERVATIONS)
    ).all()
    states: dict[str, EffectState] = {}
    for step in STEPS:
        selected = [e for e in events if e.step == step]
        intents = [e for e in selected if e.event_kind == "send_intent"]
        verified = {
            e[6] for e in selected if e.event_kind == "observation" and e.outcome == "verified"
        }
        if len(verified) > 1:
            states[step] = "conflict"
            continue
        results: list[EffectState] = []
        for intent in intents:
            outcomes = {
                e.outcome
                for e in selected
                if e.event_kind == "observation"
                and (e.attempt, e.execution_fence, e.request_digest)
                == (intent.attempt, intent.execution_fence, intent.request_digest)
            }
            result: EffectState = (
                "verified"
                if "verified" in outcomes
                else "conflict"
                if "conflict" in outcomes
                else "not_sent"
                if outcomes == {"not_sent"}
                else "unknown"
            )
            results.append(result)
        states[step] = (
            "conflict"
            if "conflict" in results
            else "unknown"
            if "unknown" in results
            else "verified"
            if verified
            else "not_sent"
            if results
            else "never"
        )
    return EffectSummary(states["branch"], states["commit"], states["pull_request"])


def _live(row: ChangeSet) -> bool:
    return (
        row.owner_id is not None
        and row.lease_expires_at is not None
        and row.lease_expires_at > datetime.now(UTC)
    )


def recovery_capabilities(session: Session, row: ChangeSet, actor_id: UUID) -> dict[str, object]:
    actor = session.get(User, actor_id)
    roles = {r.name for r in actor.roles} if actor is not None else set()
    batch = session.get(SubmissionBatch, row.batch_id)
    reviewer = bool(
        actor and actor.is_active and not actor.must_change_password and roles & REVIEW_ROLES
    )
    original_actor = bool(
        reviewer
        and batch
        and actor
        and actor.id == batch.actor_id
        and actor.token_version == batch.actor_token_version
    )
    effects = effect_summary(session, row)
    available = reviewer and row.claims_released_at is None and not _live(row)
    retry = bool(
        available
        and original_actor
        and row.status in {"failed", "blocked"}
        and not effects.unresolved
        and row.pr_id is None
    )
    reconcile = bool(
        available
        and (
            effects.unresolved
            or row.pr_id is not None
            or row.status in {"reconciling", "needs_attention"}
        )
    )
    finalize = bool(
        available
        and row.status in {"failed", "blocked", "needs_attention", "queued"}
        and not effects.unresolved
        and row.pr_id is None
        and effects.pull_request in {"never", "not_sent"}
    )
    reason = (
        "resolved"
        if row.claims_released_at is not None
        else "in_progress"
        if _live(row) or row.status in {"queued", "running"}
        else "reconciliation_required"
        if effects.unresolved
        else "original_actor_required"
        if not original_actor
        else "fresh_authority_required"
        if retry
        else None
    )
    return {
        "can_retry": retry,
        "can_reconcile": reconcile,
        "can_finalize": finalize,
        "recovery_reason": reason,
    }


def enqueue_reconciliation(change_set_id: UUID) -> None:
    from verboflex.worker.submission_tasks import run_submission_reconciliation

    run_submission_reconciliation.delay(str(change_set_id))


def _lock_action(
    session: Session, product_id: UUID, actor_id: UUID, change_set_id: UUID, expected_attempt: int
) -> ChangeSet:
    _product_actor(session, product_id, actor_id, action=True)
    row = session.scalar(
        select(ChangeSet)
        .join(SubmissionBatch)
        .where(ChangeSet.id == change_set_id, SubmissionBatch.product_id == product_id)
        .with_for_update(of=ChangeSet)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise SubmissionReviewUnavailable("submission unavailable")
    if type(expected_attempt) is not int or expected_attempt != row.attempt:
        raise SubmissionConflict("stale_attempt")
    return row


def _event(
    session: Session,
    row: ChangeSet,
    *,
    kind: str,
    outcome: str,
    actor_id: UUID | None = None,
    receipt: dict[str, object] | None = None,
) -> None:
    data = receipt or {}
    if actor_id is not None:
        data = {**data, "actor_id": str(actor_id)}
    digest = hashlib.sha256(
        json.dumps(
            [str(row.id), row.attempt, row.execution_fence, kind, outcome, data], sort_keys=True
        ).encode()
    ).hexdigest()
    session.add(
        ChangeSetEvent(
            change_set_id=row.id,
            attempt=row.attempt,
            execution_fence=row.execution_fence,
            proof_sequence=row.current_proof_sequence,
            event_kind=kind,
            step="authority",
            outcome=outcome,
            request_digest=digest,
            receipt=data,
        )
    )


def request_retry(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    change_set_id: UUID,
    expected_attempt: int,
    enqueuer: Callable[[UUID], None] = enqueue_submission,
) -> ChangeSetResponse:
    with session.begin():
        row = _lock_action(session, product_id, actor_id, change_set_id, expected_attempt)
        if not recovery_capabilities(session, row, actor_id)["can_retry"]:
            raise SubmissionConflict("retry_unavailable")
        row.attempt += 1
        row.execution_fence += 1
        row.owner_id, row.lease_expires_at = None, None
        row.status, row.error_code, row.finished_at = "queued", None, None
        row.dispatch_pending = True
        _event(
            session,
            row,
            kind="reauthorization",
            outcome="intent",
            actor_id=actor_id,
            receipt={"action": "retry"},
        )
        session.flush()
        result = change_set_response(row, session=session, actor_id=actor_id)
    with suppress(Exception):
        enqueuer(change_set_id)
    return result


def request_reconcile(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    change_set_id: UUID,
    expected_attempt: int,
    enqueuer: Callable[[UUID], None] = enqueue_reconciliation,
) -> ChangeSetResponse:
    with session.begin():
        row = _lock_action(session, product_id, actor_id, change_set_id, expected_attempt)
        if not recovery_capabilities(session, row, actor_id)["can_reconcile"]:
            raise SubmissionConflict("reconcile_unavailable")
        row.attempt += 1
        row.execution_fence += 1
        row.owner_id, row.lease_expires_at = None, None
        row.status, row.error_code, row.finished_at = "reconciling", None, None
        row.dispatch_pending = True
        _event(
            session,
            row,
            kind="reauthorization",
            outcome="intent",
            actor_id=actor_id,
            receipt={"action": "reconcile"},
        )
        session.flush()
        result = change_set_response(row, session=session, actor_id=actor_id)
    with suppress(Exception):
        enqueuer(change_set_id)
    return result


def _release(
    session: Session, row: ChangeSet, *, reason: str, actor_id: UUID | None = None
) -> None:
    row.execution_fence += 1
    row.status, row.error_code = "resolved", reason
    row.owner_id, row.lease_expires_at, row.dispatch_pending = None, None, False
    row.finished_at = row.claims_released_at = datetime.now(UTC)
    _event(
        session,
        row,
        kind="finalization",
        outcome="verified",
        actor_id=actor_id,
        receipt={"reason": reason},
    )
    session.flush()
    session.execute(
        update(ChangeSetFile)
        .where(ChangeSetFile.change_set_id == row.id, ChangeSetFile.active_claim.is_(True))
        .values(active_claim=False)
    )


def finalize_known_pre_pr(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    change_set_id: UUID,
    expected_attempt: int,
) -> ChangeSetResponse:
    with session.begin():
        row = _lock_action(session, product_id, actor_id, change_set_id, expected_attempt)
        if not recovery_capabilities(session, row, actor_id)["can_finalize"]:
            raise SubmissionConflict("finalization_unavailable")
        _release(session, row, reason="needs_review_resolved", actor_id=actor_id)
        return change_set_response(row, session=session, actor_id=actor_id)


def _exact_pr(row: ChangeSet, receipt: dict[str, object]) -> bool:
    return (
        receipt.get("id") == row.pr_id
        and receipt.get("repository_id") == str(row.provider_repository_id)
        and receipt.get("source_branch") == row.source_branch
        and receipt.get("source_commit")
        == (
            row.pr_tracking.get("source_commit")
            if row.pr_tracking is not None and receipt.get("tracking") == row.pr_tracking
            else row.commit_hash
        )
        and receipt.get("target_branch") == row.target_branch
        and receipt.get("state") == row.pr_state
    )


def release_verified_terminal_claims(session: Session, row: ChangeSet) -> bool:
    if row.claims_released_at is not None:
        return True
    if row.pr_id is None or row.pr_state not in {"MERGED", "DECLINED", "SUPERSEDED"}:
        return False
    session.flush()
    if effect_summary(session, row).unresolved:
        return False
    receipt = session.scalar(
        select(ChangeSetEvent.receipt)
        .where(
            ChangeSetEvent.change_set_id == row.id,
            ChangeSetEvent.step == "pull_request",
            ChangeSetEvent.event_kind.in_(("observation", "pr_status")),
            ChangeSetEvent.outcome == "verified",
            ChangeSetEvent.receipt["id"].as_integer() == row.pr_id,
            ChangeSetEvent.receipt["state"].as_string() == row.pr_state,
        )
        .order_by(ChangeSetEvent.created_at.desc(), ChangeSetEvent.id.desc())
        .limit(1)
    )
    if receipt is None or not _exact_pr(row, receipt):
        return False
    _release(session, row, reason="pull_request_terminal")
    return True


async def reauthorize_owned_change_set(
    factory: sessionmaker[Session],
    *,
    identity: AttemptIdentity,
    bundle: ChangeSetBundle,
    reads: SubmissionReadAdapter,
) -> tuple[AttemptIdentity, ChangeSetBundle]:
    from verboflex.services.submission_jobs import _lock_group, _owns, _require_local

    with factory.begin() as session:
        row = _lock_group(session, identity.change_set_id)
        if row is None or not _owns(row, identity) or effect_summary(session, row).unresolved:
            raise WritebackRejected(WritebackReason.STALE_BASIS)
        authorized = session.scalar(
            select(ChangeSetEvent.id)
            .where(
                ChangeSetEvent.change_set_id == row.id,
                ChangeSetEvent.attempt == identity.attempt,
                ChangeSetEvent.execution_fence == identity.execution_fence,
                ChangeSetEvent.proof_sequence == identity.proof_sequence,
                ChangeSetEvent.event_kind == "reauthorization",
                ChangeSetEvent.outcome == "intent",
                ChangeSetEvent.step == "authority",
                ChangeSetEvent.receipt["action"]
                .as_string()
                .in_(("retry", "resume_explicit_retry")),
            )
            .limit(1)
        )
        if authorized is None:
            raise WritebackRejected(WritebackReason.AUTHORITY_UNAVAILABLE)
    fresh = await prepare_writeback(
        factory, selection=bundle.group.prepared.selection, adapter=reads
    )
    original = bundle.group.prepared
    if (
        replace(
            fresh,
            authority=replace(
                fresh.authority, connection_generation=original.authority.connection_generation
            ),
            manifest_digest=original.manifest_digest,
        )
        != original
    ):
        raise WritebackRejected(WritebackReason.STALE_BASIS)
    await check_target(factory, group=bundle.group, adapter=reads)
    await revalidate_writeback_authority(factory, prepared=fresh, adapter=reads)
    new_bundle = replace(bundle, proof=fresh)
    payload = encode_prepared_writeback(fresh)
    digest = hashlib.sha256(payload).hexdigest()
    with factory.begin() as session:
        row = _lock_group(session, identity.change_set_id)
        if row is None or not _owns(row, identity) or effect_summary(session, row).unresolved:
            raise WritebackRejected(WritebackReason.STALE_BASIS)
        _require_local(session, new_bundle)
        row.current_proof_sequence += 1
        session.add(
            ChangeSetProof(
                change_set_id=row.id,
                sequence=row.current_proof_sequence,
                connection_generation=fresh.authority.connection_generation,
                proof_digest=digest,
                prepared_payload=payload,
            )
        )
        session.flush()
        _event(
            session,
            row,
            kind="reauthorization",
            outcome="verified",
            actor_id=bundle.actor_id,
            receipt={"proof_digest": digest},
        )
        return replace(identity, proof_sequence=row.current_proof_sequence), new_bundle


async def adopt_verified_admin_receipt(
    factory: sessionmaker[Session],
    *,
    actor_id: UUID,
    change_set_id: UUID,
    pull_request_id: int,
    writes: BitbucketWriteAdapter,
) -> ChangeSetResponse:
    """Worker/service entry only: a candidate ID grants no authority without exact GET evidence."""
    from verboflex.services.submission_jobs import _lock_group, _receipt_data

    with factory.begin() as session:
        row = _lock_group(session, change_set_id)
        if row is None:
            raise SubmissionReviewUnavailable("submission unavailable")
        batch = session.get(SubmissionBatch, row.batch_id)
        if batch is None:
            raise SubmissionConflict("invalid_snapshot")
        _, actor = _product_actor(session, batch.product_id, actor_id, action=True)
        if "admin" not in {r.name for r in actor.roles}:
            raise SubmissionReviewDenied("review action denied")
        if _live(row) or row.claims_released_at is not None or row.commit_hash is None:
            raise SubmissionConflict("adoption_unavailable")
        if type(pull_request_id) is not int or not 1 <= pull_request_id <= 9_007_199_254_740_991:
            raise SubmissionConflict("invalid_receipt")
        bundle = load_change_set_bundle(session, row.id)
        fence, attempt, actor_stamp = row.execution_fence, row.attempt, actor.token_version
        context = WriteContext(
            row.provider_repository_id,
            row.workspace,
            row.repository_slug,
            row.id,
            bundle.proof.authority.connection_generation,
        )
        intent = PullRequestIntent(
            context, row.commit_hash, row.target_branch, row.target_head, row.manifest_digest
        )
    with factory() as session:
        outcome = await writes.read_pull_request(
            session, intent=intent, pull_request_id=pull_request_id
        )
    receipt = outcome.receipt
    if (
        outcome.state != "verified"
        or not isinstance(receipt, PullRequestReceipt)
        or receipt.id != pull_request_id
    ):
        raise SubmissionConflict("receipt_unverified")
    with factory.begin() as session:
        row = _lock_group(session, change_set_id)
        if row is None or (row.execution_fence, row.attempt) != (fence, attempt) or _live(row):
            raise SubmissionConflict("stale_attempt")
        _, actor = _product_actor(session, bundle.product_id, actor_id, action=True)
        if actor.token_version != actor_stamp or "admin" not in {r.name for r in actor.roles}:
            raise SubmissionReviewDenied("review action denied")
        if row.pr_id is not None and row.pr_id != receipt.id:
            raise SubmissionConflict("receipt_conflict")
        if (
            receipt.repository_id,
            receipt.source_branch,
            receipt.source_commit,
            receipt.target_branch,
        ) != (row.provider_repository_id, row.source_branch, row.commit_hash, row.target_branch):
            raise SubmissionConflict("receipt_conflict")
        send = session.scalar(
            select(ChangeSetEvent)
            .where(
                ChangeSetEvent.change_set_id == row.id,
                ChangeSetEvent.step == "pull_request",
                ChangeSetEvent.event_kind == "send_intent",
            )
            .order_by(ChangeSetEvent.attempt.desc())
            .limit(1)
        )
        session.add(
            ChangeSetEvent(
                change_set_id=row.id,
                attempt=send.attempt if send else row.attempt,
                execution_fence=send.execution_fence if send else row.execution_fence,
                proof_sequence=send.proof_sequence if send else row.current_proof_sequence,
                event_kind="observation",
                step="pull_request",
                outcome="verified",
                request_digest=send.request_digest if send else row.original_proof_digest,
                receipt=_receipt_data(receipt),
                provider_status=outcome.provider_status,
            )
        )
        row.pr_id, row.pr_url, row.pr_state = receipt.id, receipt.url, receipt.state
        row.pr_target_commit, row.stage, row.status = receipt.target_commit, "complete", "succeeded"
        row.owner_id, row.lease_expires_at, row.dispatch_pending = None, None, False
        row.finished_at = datetime.now(UTC)
        _event(
            session,
            row,
            kind="finalization",
            outcome="verified",
            actor_id=actor_id,
            receipt={"action": "admin_receipt_adoption", "pull_request_id": receipt.id},
        )
        release_verified_terminal_claims(session, row)
        session.flush()
        return change_set_response(row, session=session, actor_id=actor_id)
