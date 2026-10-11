"""Independent PostgreSQL sessions prove delivery and read-only recovery ownership."""

# ruff: noqa: F811

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest
from sqlalchemy import select

from tests.integration.test_preview_jobs import (
    clean_preview_database,  # noqa: F401
    preview_session_factory,  # noqa: F401
)
from tests.integration.test_submission_jobs import Remote, accepted, run
from verboflex.integrations.bitbucket.writes import (
    BranchReceipt,
    CommitReceipt,
    PullRequestReceipt,
    WriteOutcome,
)
from verboflex.models.submission import ChangeSet, ChangeSetEvent
from verboflex.models.user import User
from verboflex.services.submission_dispatch import dispatch_pending_submissions
from verboflex.services.submission_jobs import recover_change_set


def test_queued_delivery_gap_redispatches_same_group_identity(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    _, _, identity = accepted(factory, monkeypatch)
    sends, reads = [], []

    dispatched = dispatch_pending_submissions(
        factory, enqueue_send=sends.append, enqueue_reconcile=reads.append
    )

    assert dispatched == 1
    assert sends == [identity] and reads == []
    with factory() as session:
        row = session.get(ChangeSet, identity)
        assert row.id == identity and row.status == "queued"
        assert row.source_branch == f"verboflex/change-set-{identity}"


class RecoverableRemote(Remote):
    """Separate read methods expose evidence without invoking mutation helpers."""

    def __init__(self, factory, identity):
        super().__init__(factory, identity)
        self.read_calls = []
        self.read_outcome = None
        self.pr_state = "OPEN"

    def note_read(self, session, step):
        assert not session.in_transaction()
        self.read_calls.append(step)
        return self.read_outcome

    async def reconcile_branch(self, session, *, intent):
        failure = self.note_read(session, "branch")
        return failure or WriteOutcome(
            "verified",
            "branch_verified",
            BranchReceipt(intent.context.source_branch, intent.parent),
        )

    async def reconcile_commit(self, session, *, intent):
        failure = self.note_read(session, "commit")
        return failure or WriteOutcome(
            "verified",
            "commit_verified",
            CommitReceipt(
                "b" * 40,
                intent.branch.parent,
                intent.branch.context.source_branch,
                intent.manifest_digest,
            ),
        )

    def pr_receipt(self, intent):
        return PullRequestReceipt(
            41,
            f"https://bitbucket.org/{intent.context.workspace}/{intent.context.repository_slug}/pull-requests/41",
            self.pr_state,
            intent.context.repository_id,
            intent.context.source_branch,
            intent.source_commit,
            intent.target_branch,
            "c" * 40,
        )

    async def reconcile_pull_request(self, session, *, intent):
        failure = self.note_read(session, "pull_request")
        return failure or WriteOutcome("verified", "pull_request_verified", self.pr_receipt(intent))

    async def read_pull_request(self, session, *, intent, pull_request_id, allow_rebased=False):
        assert pull_request_id == 41
        assert allow_rebased
        failure = self.note_read(session, "known_pull_request")
        return failure or WriteOutcome("verified", "pull_request_verified", self.pr_receipt(intent))

    async def read_pr_merge_status(self, session, *, context, pull_request_id):
        assert pull_request_id == 41
        self.note_read(session, "merge_status")
        return "clean"


def queue_read(factory, identity):
    with factory.begin() as session:
        row = session.get(ChangeSet, identity)
        row.status, row.dispatch_pending = "reconciling", True


def recover(factory, identity, reader, remote):
    asyncio.run(recover_change_set(factory, change_set_id=identity, reads=reader, writes=remote))


def test_broker_failure_retains_pending_same_id_for_later_dispatch(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    _, _, identity = accepted(factory, monkeypatch)
    attempted, delivered, reads = [], [], []

    def offline(value):
        attempted.append(value)
        raise ConnectionError("private broker details")

    assert (
        dispatch_pending_submissions(factory, enqueue_send=offline, enqueue_reconcile=reads.append)
        == 0
    )
    assert attempted == [identity]
    with factory.begin() as session:
        row = session.get(ChangeSet, identity)
        assert row.dispatch_pending and row.status == "queued"
        # Advance the delivery cooldown without sleeping or making a new group.
        row.last_dispatched_at = datetime.now(UTC) - timedelta(hours=1)
    assert (
        dispatch_pending_submissions(
            factory, enqueue_send=delivered.append, enqueue_reconcile=reads.append
        )
        == 1
    )
    assert delivered == [identity] and reads == []


def test_duplicate_delivery_has_one_owner_while_first_effect_is_in_flight(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    _, reader, identity = accepted(factory, monkeypatch)
    remote = RecoverableRemote(factory, identity)
    arrived, release = Event(), Event()

    def pause(step):
        if step == "branch":
            arrived.set()
            assert release.wait(15), "duplicate worker did not finish"

    remote.after = pause
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, factory, identity, reader, remote)
        try:
            assert arrived.wait(15)
            duplicate = pool.submit(run, factory, identity, reader, remote)
            duplicate.result(timeout=15)
            assert remote.calls == ["branch"]
        finally:
            release.set()
        first.result(timeout=15)
    assert remote.calls == ["branch", "commit", "pull_request"]
    with factory() as session:
        events = session.scalars(
            select(ChangeSetEvent).where(
                ChangeSetEvent.change_set_id == identity,
                ChangeSetEvent.event_kind == "send_intent",
            )
        ).all()
        assert len(events) == 3
        assert len({(event.attempt, event.execution_fence) for event in events}) == 1
        assert session.get(ChangeSet, identity).status == "succeeded"


def test_expired_inflight_send_recovers_read_only_and_late_receipt_cannot_advance_new_owner(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    _, reader, identity = accepted(factory, monkeypatch)
    remote = RecoverableRemote(factory, identity)
    arrived, release = Event(), Event()

    def pause(step):
        if step == "branch":
            arrived.set()
            assert release.wait(15), "recovery did not release old response"

    remote.after = pause
    with ThreadPoolExecutor(max_workers=1) as pool:
        original = pool.submit(run, factory, identity, reader, remote)
        try:
            assert arrived.wait(15)
            with factory.begin() as session:
                row = session.get(ChangeSet, identity)
                row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
                sent = session.scalars(
                    select(ChangeSetEvent).where(
                        ChangeSetEvent.change_set_id == identity,
                        ChangeSetEvent.event_kind == "send_intent",
                    )
                ).one()
                old_identity = (
                    sent.attempt,
                    sent.execution_fence,
                    sent.proof_sequence,
                    sent.request_digest,
                )
            sends, reads = [], []
            assert (
                dispatch_pending_submissions(
                    factory, enqueue_send=sends.append, enqueue_reconcile=reads.append
                )
                == 1
            )
            assert sends == [] and reads == [identity]
            recover(factory, identity, reader, remote)
            assert remote.read_calls == ["branch"]
            assert remote.calls == ["branch"]
            with factory() as session:
                row = session.get(ChangeSet, identity)
                assert row.branch_commit == "a" * 40 and row.stage == "commit"
                assert row.owner_id is None
                assert row.attempt > old_identity[0] and row.execution_fence > old_identity[1]
                after_recovery = (row.status, row.stage, row.attempt, row.execution_fence)
        finally:
            release.set()
        original.result(timeout=15)
    assert remote.calls == ["branch"], "late worker must not continue to commit"
    with factory() as session:
        row = session.get(ChangeSet, identity)
        assert (row.status, row.stage, row.attempt, row.execution_fence) == after_recovery
        observations = session.scalars(
            select(ChangeSetEvent).where(
                ChangeSetEvent.change_set_id == identity,
                ChangeSetEvent.event_kind == "observation",
                ChangeSetEvent.outcome == "verified",
            )
        ).all()
        assert len(observations) == 2, "both recovery and the late receipt must retain evidence"
        assert all(
            (event.attempt, event.execution_fence, event.proof_sequence, event.request_digest)
            == old_identity
            for event in observations
        )


@pytest.mark.parametrize(
    "step,reason", [("pull_request", "pull_request_not_observed"), ("commit", "branch_missing")]
)
def test_unknown_no_match_or_missing_branch_never_resends_or_recreates(
    preview_session_factory, monkeypatch, step, reason
):
    factory = preview_session_factory
    _, reader, identity = accepted(factory, monkeypatch)
    remote = RecoverableRemote(factory, identity)
    remote.failure = (step, "unknown")
    run(factory, identity, reader, remote)
    original_effects = tuple(remote.calls)
    remote.read_outcome = WriteOutcome("unknown", reason)
    queue_read(factory, identity)
    recover(factory, identity, reader, remote)
    recover(factory, identity, reader, remote)
    assert tuple(remote.calls) == original_effects
    assert remote.read_calls == [step]
    with factory() as session:
        row = session.get(ChangeSet, identity)
        assert row.pr_id is None and row.owner_id is None
        assert row.status in {"reconciling", "needs_attention"}
        assert not row.dispatch_pending
    sends, reads = [], []
    assert (
        dispatch_pending_submissions(
            factory, enqueue_send=sends.append, enqueue_reconcile=reads.append
        )
        == 0
    )
    assert sends == reads == []


@pytest.mark.parametrize("state", ["OPEN", "MERGED", "DECLINED", "SUPERSEDED"])
def test_known_pr_is_read_after_actor_revocation_and_source_branch_deletion(
    preview_session_factory, monkeypatch, state
):
    factory = preview_session_factory
    seed, reader, identity = accepted(factory, monkeypatch)
    remote = RecoverableRemote(factory, identity)
    run(factory, identity, reader, remote)
    original_effects = tuple(remote.calls)
    with factory.begin() as session:
        session.get(User, seed.actor_id).is_active = False
    reader.sessions.clear()

    async def deleted_branch(*args, **kwargs):
        raise AssertionError("known PR evidence must not depend on a deleted source branch")

    reader.resolve_repository_branch = deleted_branch
    remote.pr_state = state
    queue_read(factory, identity)
    recover(factory, identity, reader, remote)
    expected_reads = ["known_pull_request"]
    if state == "OPEN":
        expected_reads.append("merge_status")
    expected_reads.append("known_pull_request")
    assert remote.read_calls == expected_reads
    assert tuple(remote.calls) == original_effects
    assert reader.sessions == []
    with factory() as session:
        row = session.get(ChangeSet, identity)
        assert row.pr_id == 41 and row.pr_state == state
        assert row.commit_hash == "b" * 40
        assert row.pr_target_commit == "c" * 40


def test_remote_commit_success_with_failed_receipt_transaction_is_adopted_without_reposting(
    preview_session_factory, monkeypatch
):
    from verboflex.services import submission_jobs

    factory = preview_session_factory
    _, reader, identity = accepted(factory, monkeypatch)
    remote = RecoverableRemote(factory, identity)
    original_record = submission_jobs._record_outcome

    def failed_transaction(*args, **kwargs):
        if kwargs["step"] == "commit":
            assert kwargs["outcome"].state == "verified"
            raise RuntimeError("simulated receipt database outage")
        return original_record(*args, **kwargs)

    monkeypatch.setattr(submission_jobs, "_record_outcome", failed_transaction)
    with pytest.raises(RuntimeError, match="simulated receipt database outage"):
        run(factory, identity, reader, remote)
    monkeypatch.setattr(submission_jobs, "_record_outcome", original_record)
    assert remote.calls == ["branch", "commit"]
    with factory.begin() as session:
        row = session.get(ChangeSet, identity)
        assert row.commit_hash is None and row.stage == "commit"
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    sends, reads = [], []
    assert (
        dispatch_pending_submissions(
            factory, enqueue_send=sends.append, enqueue_reconcile=reads.append
        )
        == 1
    )
    assert sends == [] and reads == [identity]
    recover(factory, identity, reader, remote)
    assert remote.read_calls == ["commit"]
    assert remote.calls == ["branch", "commit"]
    with factory() as session:
        row = session.get(ChangeSet, identity)
        assert row.commit_hash == "b" * 40 and row.stage == "pull_request"
        assert row.status == "blocked" and row.owner_id is None
        sent = session.scalars(
            select(ChangeSetEvent).where(
                ChangeSetEvent.change_set_id == identity,
                ChangeSetEvent.step == "commit",
                ChangeSetEvent.event_kind == "send_intent",
            )
        ).one()
        observed = session.scalars(
            select(ChangeSetEvent).where(
                ChangeSetEvent.change_set_id == identity,
                ChangeSetEvent.step == "commit",
                ChangeSetEvent.event_kind == "observation",
            )
        ).one()
        assert observed.outcome == "verified"
        assert (observed.attempt, observed.execution_fence, observed.request_digest) == (
            sent.attempt,
            sent.execution_fence,
            sent.request_digest,
        )


@pytest.mark.parametrize("step", ["branch", "commit"])
def test_crash_after_positive_read_recovery_cannot_dispatch_a_new_write(
    preview_session_factory, monkeypatch, step
):
    from verboflex.services import submission_jobs
    from verboflex.services.submission_recovery import request_reconcile

    class WorkerDeath(BaseException):
        pass

    factory = preview_session_factory
    seed, reader, identity = accepted(factory, monkeypatch)
    remote = RecoverableRemote(factory, identity)
    remote.failure = (step, "unknown")
    run(factory, identity, reader, remote)
    with factory() as session:
        attempt = session.get(ChangeSet, identity).attempt
    with factory() as session:
        request_reconcile(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            change_set_id=identity,
            expected_attempt=attempt,
            enqueuer=lambda _: None,
        )
    original_record = submission_jobs._record_outcome

    def die_after_record(*args, **kwargs):
        result = original_record(*args, **kwargs)
        assert result is True and kwargs["outcome"].state == "verified"
        raise WorkerDeath()

    monkeypatch.setattr(submission_jobs, "_record_outcome", die_after_record)
    with pytest.raises(WorkerDeath):
        recover(factory, identity, reader, remote)
    monkeypatch.setattr(submission_jobs, "_record_outcome", original_record)
    with factory.begin() as session:
        row = session.get(ChangeSet, identity)
        assert row.status == "running"
        assert row.stage == ("commit" if step == "branch" else "pull_request")
        assert row.branch_commit == "a" * 40
        if step == "commit":
            assert row.commit_hash == "b" * 40
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    sends, reads = [], []
    assert (
        dispatch_pending_submissions(
            factory, enqueue_send=sends.append, enqueue_reconcile=reads.append
        )
        == 0
    )
    assert sends == [] and reads == [], "read-only recovery is not explicit write authorization"
    assert remote.calls == (["branch"] if step == "branch" else ["branch", "commit"])
    assert remote.read_calls == [step]
    with factory() as session:
        row = session.get(ChangeSet, identity)
        assert row.status == "blocked" and row.error_code == "recovered_review_required"
        assert row.owner_id is None and not row.dispatch_pending
        authority_events = session.scalars(
            select(ChangeSetEvent).where(
                ChangeSetEvent.change_set_id == identity,
                ChangeSetEvent.event_kind == "reauthorization",
                ChangeSetEvent.step == "authority",
            )
        ).all()
        assert any(event.receipt.get("action") == "reconcile" for event in authority_events)
        assert all(
            event.receipt.get("action") != "resume_explicit_retry" for event in authority_events
        )
