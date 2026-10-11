"""Short ownership transactions around generation-bound immutable external effects.

Intent is committed before calling the provider. Any unfinished intent survives
worker death and lease expiry; neither event authorizes another mutation.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.integrations.bitbucket.writes import (
    BitbucketWriteAdapter,
    BranchIntent,
    BranchReceipt,
    CommitFile,
    CommitIntent,
    CommitReceipt,
    PullRequestIntent,
    PullRequestReceipt,
    WriteContext,
    WriteOutcome,
)
from verboflex.localization.writing.core import WritebackReason, WritebackRejected
from verboflex.models.product import Product
from verboflex.models.submission import ChangeSet, ChangeSetEvent, SubmissionBatch
from verboflex.services.submission_selection import SubmissionReadAdapter, check_target
from verboflex.services.submissions import ChangeSetBundle, load_change_set_bundle
from verboflex.services.writeback import (
    _normalize,
    revalidate_writeback_authority,
)
from verboflex.services.writeback_authority import capture_writeback_authority

Step = Literal["branch", "commit", "pull_request"]
Receipt = BranchReceipt | CommitReceipt | PullRequestReceipt
Intent = BranchIntent | CommitIntent | PullRequestIntent
LEASE_DURATION = timedelta(minutes=6)


@dataclass(frozen=True, slots=True)
class AttemptIdentity:
    change_set_id: UUID
    product_id: UUID
    owner_id: UUID
    attempt: int
    execution_fence: int
    proof_sequence: int


@dataclass(frozen=True, slots=True)
class SendEvidence:
    attempt: int
    execution_fence: int
    proof_sequence: int
    request_digest: str


async def recover_change_set(
    factory: sessionmaker[Session],
    *,
    change_set_id: UUID,
    reads: SubmissionReadAdapter,
    writes: BitbucketWriteAdapter,
) -> None:
    """Read exact old intent; positive recovery never grants another mutation."""
    from verboflex.services.submission_recovery import (
        effect_summary,
        release_verified_terminal_claims,
    )

    claimed = _claim(factory, change_set_id, reconcile=True)
    if claimed is None:
        return
    identity, bundle = claimed
    with factory() as session:
        row = session.get(ChangeSet, change_set_id)
        if row is None or not _owns(row, identity):
            return
        effects = effect_summary(session, row)
        if not effects.bounded:
            _stop(factory, identity, code="evidence_limit", attention=True)
            return
        step = cast(Step, "pull_request" if row.pr_id is not None else row.stage)
        if step not in {"branch", "commit", "pull_request"}:
            _stop(factory, identity, code="invalid_snapshot", attention=True)
            return
        commit_hash, pr_id = row.commit_hash, row.pr_id
        old = session.scalar(
            select(ChangeSetEvent)
            .where(
                ChangeSetEvent.change_set_id == change_set_id,
                ChangeSetEvent.step == step,
                ChangeSetEvent.event_kind == "send_intent",
            )
            .order_by(ChangeSetEvent.attempt.desc(), ChangeSetEvent.created_at.desc())
            .limit(1)
        )
        evidence = (
            SendEvidence(old.attempt, old.execution_fence, old.proof_sequence, old.request_digest)
            if old is not None
            else None
        )
    # Actor revocation or credential renewal never prevents collecting read-only evidence.
    digest = evidence.request_digest if evidence else _request_digest(bundle, step, commit_hash)
    if pr_id is not None:
        from verboflex.services.submission_tracking import track_pull_request

        intent = _intent(bundle, "pull_request", commit_hash)
        assert isinstance(intent, PullRequestIntent)
        await track_pull_request(
            factory,
            identity=identity,
            bundle=bundle,
            writes=writes,
            intent=intent,
            pull_request_id=pr_id,
            digest=digest,
        )
        return
    try:
        intent = _intent(bundle, step, commit_hash)
        with factory() as session:
            if isinstance(intent, BranchIntent):
                outcome = cast(
                    WriteOutcome[Receipt], await writes.reconcile_branch(session, intent=intent)
                )
            elif isinstance(intent, CommitIntent):
                outcome = cast(
                    WriteOutcome[Receipt], await writes.reconcile_commit(session, intent=intent)
                )
            else:
                outcome = cast(
                    WriteOutcome[Receipt],
                    await writes.reconcile_pull_request(session, intent=intent),
                )
    except Exception:
        outcome = WriteOutcome("unknown", "provider_unavailable")
    if outcome.state == "not_sent":
        # Failure to perform a read says nothing about the original send.
        outcome = WriteOutcome(
            "unknown", "incomplete_verification", provider_status=outcome.provider_status
        )
    if not _record_outcome(
        factory,
        identity,
        step=step,
        digest=digest,
        outcome=outcome,
        evidence=evidence,
        refresh_pr=pr_id is not None,
    ):
        return
    with factory.begin() as session:
        row = _lock_group(session, change_set_id)
        if row is None or not _owns(row, identity):
            return
        effects = effect_summary(session, row)
        if effects.unresolved:
            row.status, row.error_code = "needs_attention", "unresolved_evidence"
        elif row.stage == "complete":
            if release_verified_terminal_claims(session, row):
                return
            row.status, row.error_code = "succeeded", None
        else:
            row.status, row.error_code = "blocked", "recovered_review_required"
        row.finished_at = datetime.now(UTC)
        _clear_owner(row)


def _lock_group(session: Session, change_set_id: UUID) -> ChangeSet | None:
    product_id = session.scalar(
        select(SubmissionBatch.product_id)
        .join(ChangeSet, ChangeSet.batch_id == SubmissionBatch.id)
        .where(ChangeSet.id == change_set_id)
    )
    if product_id is None:
        return None
    session.execute(select(Product.id).where(Product.id == product_id).with_for_update()).one()
    return session.scalar(
        select(ChangeSet)
        .where(ChangeSet.id == change_set_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _owns(row: ChangeSet, identity: AttemptIdentity) -> bool:
    return (
        row.owner_id == identity.owner_id
        and row.attempt == identity.attempt
        and row.execution_fence == identity.execution_fence
        and row.current_proof_sequence == identity.proof_sequence
        and row.claims_released_at is None
        and row.lease_expires_at is not None
        and row.lease_expires_at > datetime.now(UTC)
        and row.status == "running"
    )


def _clear_owner(row: ChangeSet) -> None:
    row.owner_id = None
    row.lease_expires_at = None
    row.dispatch_pending = False


def _claim(
    factory: sessionmaker[Session], change_set_id: UUID, *, reconcile: bool = False
) -> tuple[AttemptIdentity, ChangeSetBundle] | None:
    with factory.begin() as session:
        row = _lock_group(session, change_set_id)
        expected = "reconciling" if reconcile else "queued"
        if row is None or row.status != expected or row.owner_id is not None:
            return None
        if reconcile and not row.dispatch_pending:
            return None
        if row.claims_released_at is not None:
            return None
        try:
            bundle = load_change_set_bundle(session, change_set_id)
        except ValueError, LookupError:
            row.status, row.error_code = "blocked", "stale_basis"
            _clear_owner(row)
            return None
        row.status, row.error_code = "running", None
        row.owner_id = uuid4()
        row.lease_expires_at = datetime.now(UTC) + LEASE_DURATION
        row.started_at, row.finished_at = datetime.now(UTC), None
        row.dispatch_pending = False
        identity = AttemptIdentity(
            row.id,
            bundle.product_id,
            row.owner_id,
            row.attempt,
            row.execution_fence,
            row.current_proof_sequence,
        )
        if reconcile:
            session.add(
                ChangeSetEvent(
                    change_set_id=row.id,
                    attempt=row.attempt,
                    execution_fence=row.execution_fence,
                    proof_sequence=row.current_proof_sequence,
                    event_kind="reauthorization",
                    step="authority",
                    outcome="verified",
                    request_digest=row.original_proof_digest,
                    receipt={"action": "reconciliation_started"},
                )
            )
        return identity, bundle


def _require_local(
    session: Session, bundle: ChangeSetBundle, *, allow_expired_connection: bool = False
) -> None:
    current = _normalize(
        capture_writeback_authority(
            session,
            selection=bundle.proof.selection,
            allow_expired_connection=allow_expired_connection,
        )
    )
    if (
        current != bundle.proof.authority
        or current.actor_id != bundle.actor_id
        or current.actor_token_version != bundle.actor_token_version
        or not {"admin", "product_manager_reviewer"}.intersection(current.roles)
    ):
        raise WritebackRejected(WritebackReason.STALE_BASIS)


async def _preflight(
    factory: sessionmaker[Session], bundle: ChangeSetBundle, reads: SubmissionReadAdapter
) -> None:
    # This performs ordinary read credential renewal before binding the send.
    # A changed generation invalidates the frozen proof rather than replacing it.
    with factory.begin() as session:
        _require_local(session, bundle, allow_expired_connection=True)
    await check_target(factory, group=bundle.group, adapter=reads, files=False)
    await revalidate_writeback_authority(factory, prepared=bundle.proof, adapter=reads)
    await check_target(factory, group=bundle.group, adapter=reads)


def _stop(
    factory: sessionmaker[Session], identity: AttemptIdentity, *, code: str, attention: bool = False
) -> None:
    with factory.begin() as session:
        row = _lock_group(session, identity.change_set_id)
        if row is not None and _owns(row, identity):
            row.status = "needs_attention" if attention or row.pr_id is not None else "blocked"
            row.error_code, row.finished_at = code, datetime.now(UTC)
            _clear_owner(row)


def _intent(bundle: ChangeSetBundle, step: Step, commit_hash: str | None) -> Intent:
    group = bundle.group
    context = WriteContext(
        group.provider_repository_id,
        group.workspace,
        group.repository_slug,
        group.id,
        bundle.proof.authority.connection_generation,
    )
    branch = BranchIntent(context, group.target_head)
    if step == "branch":
        return branch
    if step == "commit":
        files = []
        for file in group.prepared.files:
            if file.attributes is None:
                raise WritebackRejected(WritebackReason.UNSUPPORTED_FILE_ATTRIBUTES)
            files.append(
                CommitFile(file.authority.path, file.content, file.before_sha256, file.attributes)
            )
        return CommitIntent(
            branch,
            group.prepared.manifest_digest,
            tuple(files),
        )
    if commit_hash is None:
        raise WritebackRejected(WritebackReason.STALE_BASIS)
    return PullRequestIntent(
        context, commit_hash, group.target_branch, group.target_head, group.prepared.manifest_digest
    )


def _request_digest(bundle: ChangeSetBundle, step: Step, commit_hash: str | None) -> str:
    group = bundle.group
    body = {
        "version": 1,
        "step": step,
        "change_set_id": str(group.id),
        "repository_id": str(group.repository_id),
        "provider_repository_id": str(group.provider_repository_id),
        "target_branch": group.target_branch,
        "target_head": group.target_head,
        "source_branch": group.source_branch,
        "source_commit": commit_hash,
        "manifest_digest": group.prepared.manifest_digest,
        "proof_digest": bundle.proof.manifest_digest,
        "generation": bundle.proof.authority.connection_generation,
    }
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _unsettled_step(session: Session, row: ChangeSet, step: Step) -> bool:
    """Only a positive not-sent observation can allow a subsequent send."""
    from verboflex.services.submission_recovery import effect_summary

    effects = effect_summary(session, row)
    return effects.unresolved or getattr(effects, step) not in {"never", "not_sent"}


def _begin_send(
    factory: sessionmaker[Session],
    identity: AttemptIdentity,
    bundle: ChangeSetBundle,
    step: Step,
    digest: str,
) -> bool:
    with factory.begin() as session:
        row = _lock_group(session, identity.change_set_id)
        if row is None or not _owns(row, identity) or row.stage != step:
            return False
        # Product lock already held: capture takes sorted scope, actor and proposal locks.
        _require_local(session, bundle)
        if _unsettled_step(session, row, step):
            row.status, row.error_code = "reconciling", "reconciliation_required"
            _clear_owner(row)
            return False
        row.lease_expires_at = datetime.now(UTC) + LEASE_DURATION
        session.add(
            ChangeSetEvent(
                change_set_id=row.id,
                attempt=identity.attempt,
                execution_fence=identity.execution_fence,
                proof_sequence=identity.proof_sequence,
                event_kind="send_intent",
                step=step,
                outcome="intent",
                request_digest=digest,
                receipt={},
                provider_status=None,
            )
        )
        return True


def _authorize_send(
    factory: sessionmaker[Session],
    identity: AttemptIdentity,
    bundle: ChangeSetBundle,
    step: Step,
    digest: str,
) -> bool:
    """Last synchronous check after adapter preflight, immediately before its POST."""
    with factory.begin() as session:
        row = _lock_group(session, identity.change_set_id)
        if row is None or not _owns(row, identity) or row.stage != step:
            return False
        try:
            _require_local(session, bundle)
        except WritebackRejected:
            return False
        return (
            session.scalar(
                select(ChangeSetEvent.id).where(
                    ChangeSetEvent.change_set_id == row.id,
                    ChangeSetEvent.attempt == identity.attempt,
                    ChangeSetEvent.execution_fence == identity.execution_fence,
                    ChangeSetEvent.proof_sequence == identity.proof_sequence,
                    ChangeSetEvent.step == step,
                    ChangeSetEvent.event_kind == "send_intent",
                    ChangeSetEvent.outcome == "intent",
                    ChangeSetEvent.request_digest == digest,
                )
            )
            is not None
        )


def _receipt_data(receipt: Receipt | None) -> dict[str, object]:
    if isinstance(receipt, BranchReceipt):
        return {"name": receipt.name, "commit_hash": receipt.commit_hash}
    if isinstance(receipt, CommitReceipt):
        return {
            "commit_hash": receipt.commit_hash,
            "parent": receipt.parent,
            "branch": receipt.branch,
            "manifest_digest": receipt.manifest_digest,
        }
    if isinstance(receipt, PullRequestReceipt):
        return {
            "id": receipt.id,
            "url": receipt.url,
            "state": receipt.state,
            "repository_id": str(receipt.repository_id),
            "source_branch": receipt.source_branch,
            "source_commit": receipt.source_commit,
            "target_branch": receipt.target_branch,
            "target_commit": receipt.target_commit,
        }
    return {}


def _record_outcome(
    factory: sessionmaker[Session],
    identity: AttemptIdentity,
    *,
    step: Step,
    digest: str,
    outcome: WriteOutcome[Receipt],
    evidence: SendEvidence | None = None,
    refresh_pr: bool = False,
) -> bool:
    """Append evidence even if a newer owner/fence prevents this attempt advancing."""
    with factory.begin() as session:
        row = _lock_group(session, identity.change_set_id)
        if row is None:
            return False
        session.add(
            ChangeSetEvent(
                change_set_id=row.id,
                attempt=evidence.attempt if evidence else identity.attempt,
                execution_fence=evidence.execution_fence if evidence else identity.execution_fence,
                proof_sequence=evidence.proof_sequence if evidence else identity.proof_sequence,
                event_kind="observation",
                step=step,
                outcome=outcome.state,
                request_digest=evidence.request_digest if evidence else digest,
                receipt=_receipt_data(outcome.receipt),
                provider_status=outcome.provider_status,
            )
        )
        if not _owns(row, identity) or not (
            row.stage == step or (refresh_pr and step == "pull_request" and row.stage == "complete")
        ):
            return False
        if outcome.state == "verified" and outcome.receipt is not None:
            receipt = outcome.receipt
            if step == "branch" and isinstance(receipt, BranchReceipt):
                row.branch_commit, row.stage = receipt.commit_hash, "commit"
            elif step == "commit" and isinstance(receipt, CommitReceipt):
                row.commit_hash, row.stage = receipt.commit_hash, "pull_request"
            elif step == "pull_request" and isinstance(receipt, PullRequestReceipt):
                if row.pr_id is not None and (
                    row.pr_id != receipt.id
                    or (
                        row.pr_state in {"MERGED", "DECLINED", "SUPERSEDED"}
                        and row.pr_state != receipt.state
                    )
                ):
                    row.status, row.error_code = "needs_attention", "provider_conflict"
                    _clear_owner(row)
                    return False
                row.pr_id, row.pr_url, row.pr_state = receipt.id, receipt.url, receipt.state
                row.pr_target_commit, row.stage = receipt.target_commit, "complete"
            else:
                row.status, row.error_code = "needs_attention", "invalid_provider_response"
                _clear_owner(row)
                return False
            row.error_code = None
            row.lease_expires_at = datetime.now(UTC) + LEASE_DURATION
            return True
        row.status = {
            "not_sent": "failed",
            "unknown": "reconciling",
            "conflict": "needs_attention",
        }.get(outcome.state, "needs_attention")
        # Persist only a closed local reason, never provider text or exception details.
        row.error_code = {
            "not_sent": "provider_not_sent",
            "unknown": "reconciliation_required",
            "conflict": "provider_conflict",
        }.get(outcome.state, "invalid_provider_response")
        row.finished_at = datetime.now(UTC)
        _clear_owner(row)
        return False


async def _send(
    factory: sessionmaker[Session],
    writes: BitbucketWriteAdapter,
    intent: Intent,
    before_send: Callable[[], bool],
) -> WriteOutcome[Receipt]:
    with factory() as session:
        if isinstance(intent, BranchIntent):
            return cast(
                WriteOutcome[Receipt],
                await writes.create_branch(session, intent=intent, before_send=before_send),
            )
        if isinstance(intent, CommitIntent):
            return cast(
                WriteOutcome[Receipt],
                await writes.create_commit(session, intent=intent, before_send=before_send),
            )
        return cast(
            WriteOutcome[Receipt],
            await writes.create_pull_request(session, intent=intent, before_send=before_send),
        )


async def execute_change_set(
    factory: sessionmaker[Session],
    *,
    change_set_id: UUID,
    reads: SubmissionReadAdapter,
    writes: BitbucketWriteAdapter,
) -> None:
    """Execute one accepted group; queue payload contains only its UUID."""
    claimed = _claim(factory, change_set_id)
    if claimed is None:
        return
    identity, bundle = claimed
    with factory() as session:
        explicit_retry = (
            session.scalar(
                select(ChangeSetEvent.id)
                .where(
                    ChangeSetEvent.change_set_id == change_set_id,
                    ChangeSetEvent.attempt == identity.attempt,
                    ChangeSetEvent.execution_fence == identity.execution_fence,
                    ChangeSetEvent.event_kind == "reauthorization",
                    ChangeSetEvent.step == "authority",
                    ChangeSetEvent.outcome == "intent",
                    ChangeSetEvent.receipt["action"]
                    .as_string()
                    .in_(("retry", "resume_explicit_retry")),
                )
                .limit(1)
            )
            is not None
        )
    if explicit_retry:
        from verboflex.services.submission_recovery import reauthorize_owned_change_set

        try:
            identity, bundle = await reauthorize_owned_change_set(
                factory, identity=identity, bundle=bundle, reads=reads
            )
        except WritebackRejected as error:
            _stop(factory, identity, code=error.reason.value)
            return
        except Exception:
            _stop(factory, identity, code="provider_unavailable")
            return
    for _ in range(3):
        with factory() as session:
            row = session.get(ChangeSet, change_set_id)
            if row is None or not _owns(row, identity):
                return
            step, commit_hash = row.stage, row.commit_hash
        if step not in {"branch", "commit", "pull_request"}:
            break
        current_step = cast(Step, step)
        try:
            await _preflight(factory, bundle, reads)
            intent = _intent(bundle, current_step, commit_hash)
            digest = _request_digest(bundle, current_step, commit_hash)
            if not _begin_send(factory, identity, bundle, current_step, digest):
                return
        except WritebackRejected as error:
            _stop(factory, identity, code=error.reason.value)
            return
        except Exception:
            _stop(factory, identity, code="provider_unavailable")
            return
        try:
            outcome = await _send(
                factory,
                writes,
                intent,
                partial(_authorize_send, factory, identity, bundle, current_step, digest),
            )
        except Exception:
            # The committed intent is conservative even if an adapter unexpectedly raises.
            outcome = WriteOutcome("unknown", "provider_unavailable")
        if not _record_outcome(
            factory, identity, step=current_step, digest=digest, outcome=outcome
        ):
            return
        try:
            # Retain receipt before checking revocation/branch movement after the effect.
            await _preflight(factory, bundle, reads)
        except WritebackRejected as error:
            _stop(factory, identity, code=error.reason.value)
            return
        except Exception:
            _stop(factory, identity, code="provider_unavailable")
            return
    with factory.begin() as session:
        row = _lock_group(session, change_set_id)
        if row is not None and _owns(row, identity) and row.stage == "complete":
            row.status, row.error_code = "succeeded", None
            row.finished_at = datetime.now(UTC)
            _clear_owner(row)
