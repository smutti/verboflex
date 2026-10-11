"""Real PostgreSQL journal and authority around independent remote effects."""

# ruff: noqa: F811

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.integration.test_preview_jobs import (
    clean_preview_database,  # noqa: F401
    preview_session_factory,  # noqa: F401
)
from tests.integration.test_submission_review_jobs import create, get
from tests.integration.test_writeback_authority import PreparedSource, seed_writeback_authority
from verboflex.integrations.bitbucket.writes import (
    BranchReceipt,
    CommitReceipt,
    PullRequestReceipt,
    WriteOutcome,
)
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.review import TranslationProposal
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.services.submission_jobs import execute_change_set
from verboflex.services.submission_reviews import execute_submission_review


def accepted(factory, monkeypatch, *, seed=None, reader=None):
    from verboflex.schemas.submissions import CreateSubmissionBatchRequest
    from verboflex.services.submissions import create_submission_batch

    seed = seed or seed_writeback_authority(factory, monkeypatch)
    reader = reader or PreparedSource(seed)
    review = create(factory, seed)
    asyncio.run(execute_submission_review(factory, review_id=review.id, adapter=reader))
    ready = get(factory, seed, review.id)
    assert ready.state == "ready", ready.error_code
    with factory() as session:
        batch = create_submission_batch(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request=CreateSubmissionBatchRequest(
                review_id=ready.id,
                expected_review_attempt=ready.attempt,
                expected_content_digest=ready.manifest_digest,
                request_key=uuid4(),
            ),
            enqueuer=lambda _: None,
        )
    return seed, reader, batch.groups[0].id


class Remote:
    """Records actual effects only after independently observing committed send intent."""

    def __init__(self, factory, identity):
        self.factory, self.identity = factory, identity
        self.calls = []
        self.after = lambda _: None
        self.failure = None

    def observe(self, session, step, context):
        from verboflex.models.submission import ChangeSet, ChangeSetEvent

        assert not session.in_transaction()
        with self.factory() as other:
            group = other.get(ChangeSet, self.identity)
            assert context.repository_id == group.provider_repository_id
            assert context.repository_id != group.repository_id
            intent = other.scalar(
                select(ChangeSetEvent).where(
                    ChangeSetEvent.change_set_id == self.identity,
                    ChangeSetEvent.step == step,
                    ChangeSetEvent.event_kind == "send_intent",
                )
            )
            assert intent is not None, "external effect preceded durable intent"
        self.calls.append(step)
        self.after(step)
        if self.failure and self.failure[0] == step:
            return WriteOutcome(self.failure[1], "timeout")
        return None

    async def create_branch(self, session, *, intent, before_send):
        assert before_send()
        failed = self.observe(session, "branch", intent.context)
        return failed or WriteOutcome(
            "verified",
            "branch_verified",
            BranchReceipt(intent.context.source_branch, intent.parent),
        )

    async def create_commit(self, session, *, intent, before_send):
        assert before_send()
        failed = self.observe(session, "commit", intent.branch.context)
        return failed or WriteOutcome(
            "verified",
            "commit_verified",
            CommitReceipt(
                "b" * 40,
                intent.branch.parent,
                intent.branch.context.source_branch,
                intent.manifest_digest,
            ),
        )

    async def create_pull_request(self, session, *, intent, before_send):
        assert before_send()
        failed = self.observe(session, "pull_request", intent.context)
        return failed or WriteOutcome(
            "verified",
            "pull_request_verified",
            PullRequestReceipt(
                41,
                f"https://bitbucket.org/{intent.context.workspace}/{intent.context.repository_slug}/pull-requests/41",
                "OPEN",
                intent.context.repository_id,
                intent.context.source_branch,
                intent.source_commit,
                intent.target_branch,
                intent.target_head,
            ),
        )


def run(factory, identity, reader, remote):
    asyncio.run(execute_change_set(factory, change_set_id=identity, reads=reader, writes=remote))


def test_explicit_accepted_group_journals_each_effect_and_duplicate_delivery_is_noop(
    preview_session_factory, monkeypatch
):
    from verboflex.models.submission import ChangeSet, ChangeSetEvent

    factory = preview_session_factory
    seed, reader, identity = accepted(factory, monkeypatch)
    remote = Remote(factory, identity)
    run(factory, identity, reader, remote)
    assert remote.calls == ["branch", "commit", "pull_request"]
    run(factory, identity, reader, remote)
    assert len(remote.calls) == 3
    with factory() as session:
        row = session.get(ChangeSet, identity)
        assert row.status == "succeeded" and row.stage == "complete"
        assert row.pr_id == 41 and row.commit_hash == "b" * 40
        assert row.owner_id is None and not row.dispatch_pending
        assert session.get(TranslationProposal, seed.proposal_id).version == seed.version
        events = list(
            session.scalars(select(ChangeSetEvent).where(ChangeSetEvent.change_set_id == identity))
        )
        assert [e.outcome for e in events if e.event_kind == "observation"].count("verified") == 3


@pytest.mark.parametrize(
    "mutation", ["disabled", "roles", "token", "password", "version", "generation"]
)
def test_current_authority_loss_before_first_send_stops_all_effects(
    preview_session_factory, monkeypatch, mutation
):
    from verboflex.models.submission import ChangeSet

    factory = preview_session_factory
    seed, reader, identity = accepted(factory, monkeypatch)
    with factory.begin() as session:
        actor = session.get(User, seed.actor_id)
        if mutation == "disabled":
            actor.is_active = False
        elif mutation == "roles":
            actor.roles = [session.scalar(select(Role).where(Role.name == "viewer"))]
        elif mutation == "token":
            actor.token_version += 1
        elif mutation == "password":
            actor.must_change_password = True
        elif mutation == "version":
            session.get(TranslationProposal, seed.proposal_id).version += 1
        else:
            session.get(BitbucketConnection, 1).generation += 1
    remote = Remote(factory, identity)
    run(factory, identity, reader, remote)
    assert remote.calls == []
    with factory() as session:
        assert session.get(ChangeSet, identity).status == "blocked"


@pytest.mark.parametrize("step", ["branch", "commit", "pull_request"])
def test_post_send_revocation_retains_receipt_and_prevents_later_effects(
    preview_session_factory, monkeypatch, step
):
    from verboflex.models.submission import ChangeSet, ChangeSetEvent

    factory = preview_session_factory
    seed, reader, identity = accepted(factory, monkeypatch)
    remote = Remote(factory, identity)

    def revoke(current):
        if current == step:
            with factory.begin() as session:
                session.get(User, seed.actor_id).is_active = False

    remote.after = revoke
    run(factory, identity, reader, remote)
    assert remote.calls[-1] == step
    with factory() as session:
        row = session.get(ChangeSet, identity)
        assert row.status in {"blocked", "needs_attention"}
        evidence = session.scalar(
            select(ChangeSetEvent).where(
                ChangeSetEvent.change_set_id == identity,
                ChangeSetEvent.step == step,
                ChangeSetEvent.outcome == "verified",
            )
        )
        assert evidence is not None and evidence.receipt
        if step == "pull_request":
            assert row.pr_id == 41


@pytest.mark.parametrize("step", ["branch", "commit", "pull_request"])
def test_unknown_send_stops_and_duplicate_queue_delivery_never_reposts(
    preview_session_factory, monkeypatch, step
):
    from verboflex.models.submission import ChangeSet

    factory = preview_session_factory
    _, reader, identity = accepted(factory, monkeypatch)
    remote = Remote(factory, identity)
    remote.failure = (step, "unknown")
    run(factory, identity, reader, remote)
    count = len(remote.calls)
    run(factory, identity, reader, remote)
    assert len(remote.calls) == count and remote.calls[-1] == step
    with factory() as session:
        row = session.get(ChangeSet, identity)
        assert row.status == "reconciling" and row.stage == step


def test_generation_renewal_before_send_blocks_stale_prepared(preview_session_factory, monkeypatch):
    from verboflex.models.submission import ChangeSet

    factory = preview_session_factory
    _, reader, identity = accepted(factory, monkeypatch)
    original = reader.resolve_repository_branch
    renewed = False

    async def renew(session, **kwargs):
        nonlocal renewed
        if not renewed:
            renewed = True
            with factory.begin() as other:
                other.get(BitbucketConnection, 1).generation += 1
        return await original(session, **kwargs)

    reader.resolve_repository_branch = renew
    remote = Remote(factory, identity)
    run(factory, identity, reader, remote)
    assert renewed and remote.calls == []
    with factory() as session:
        assert session.get(ChangeSet, identity).status == "blocked"


@pytest.mark.parametrize("when", ["before", "after_commit", "after_pr"])
def test_selected_target_movement_blocks_later_effects_but_keeps_receipts(
    preview_session_factory, monkeypatch, when
):
    from verboflex.integrations.bitbucket.client import BitbucketBranch
    from verboflex.models.submission import ChangeSet

    factory = preview_session_factory
    _, reader, identity = accepted(factory, monkeypatch)
    original = reader.resolve_repository_branch
    changed = when == "before"

    async def resolve(session, **kwargs):
        if changed and kwargs["branch"] == "release/1":
            return BitbucketBranch(kwargs["branch"], "c" * 40)
        return await original(session, **kwargs)

    def advance(step):
        nonlocal changed
        if (when, step) in {("after_commit", "commit"), ("after_pr", "pull_request")}:
            changed = True

    reader.resolve_repository_branch = resolve
    remote = Remote(factory, identity)
    remote.after = advance
    run(factory, identity, reader, remote)
    expected = {
        "before": [],
        "after_commit": ["branch", "commit"],
        "after_pr": ["branch", "commit", "pull_request"],
    }
    assert remote.calls == expected[when]
    with factory() as session:
        row = session.get(ChangeSet, identity)
        assert row.status in {"blocked", "needs_attention"}
        if when == "after_pr":
            assert row.pr_id == 41


def test_newer_proposal_after_pr_response_survives_old_completion(
    preview_session_factory, monkeypatch
):
    from verboflex.models.submission import ChangeSet, ChangeSetItem

    factory = preview_session_factory
    seed, reader, identity = accepted(factory, monkeypatch)
    remote = Remote(factory, identity)

    def save_newer(step):
        if step == "pull_request":
            with factory.begin() as session:
                proposal = session.get(TranslationProposal, seed.proposal_id)
                proposal.version += 1
                proposal.state = "draft"

    remote.after = save_newer
    run(factory, identity, reader, remote)
    with factory() as session:
        assert session.get(ChangeSet, identity).pr_id == 41
        proposal = session.get(TranslationProposal, seed.proposal_id)
        assert proposal.version == seed.version + 1 and proposal.state == "draft"
        item = session.scalar(select(ChangeSetItem).where(ChangeSetItem.change_set_id == identity))
        assert item.proposal_version == seed.version


def test_submission_task_is_json_uuid_only_and_acknowledges_after_execution(monkeypatch):
    from verboflex.worker import submission_tasks

    called = []

    async def record(identity):
        called.append(identity)

    monkeypatch.setattr(submission_tasks, "_submit", record)
    task = submission_tasks.run_submission
    for invalid in ("invalid", {}, None, 42):
        task.run(invalid)
    assert called == []
    identity = uuid4()
    task.run(str(identity))
    assert called == [identity]
    assert task.serializer == "json" and task.acks_late and task.reject_on_worker_lost
