"""Live rebases never rewrite immutable receipts or authorize a second send."""

import asyncio

import pytest
from sqlalchemy import select

from tests.api.test_submission_reviews import review_api as review_api
from tests.api.test_submissions import ready_api as ready_api
from tests.integration.test_preview_jobs import clean_preview_database as clean_preview_database
from tests.integration.test_preview_jobs import preview_session_factory as preview_session_factory
from tests.integration.test_submission_jobs import Remote
from tests.integration.test_submission_recovery import accepted as accepted
from tests.integration.test_submission_recovery import action
from tests.integration.test_writeback_authority import PreparedSource
from verboflex.integrations.bitbucket.writes import PullRequestReceipt, WriteOutcome, _WireError
from verboflex.models.submission import ChangeSet, ChangeSetEvent, ChangeSetFile
from verboflex.services import submission_jobs
from verboflex.services.submission_recovery import effect_summary, request_reconcile
from verboflex.services.submissions import load_change_set_bundle


class TrackingRemote(Remote):
    merge_status = "clean"
    state = "OPEN"
    source = "c" * 40
    fault = None
    reads = 0
    verified = 0

    async def read_pull_request(self, session, *, intent, pull_request_id, allow_rebased=False):
        assert not session.in_transaction()
        assert allow_rebased and pull_request_id == 41
        self.reads += 1
        if self.fault == "unavailable":
            return WriteOutcome("unknown", "timeout")
        return WriteOutcome(
            "verified",
            "pull_request_verified",
            PullRequestReceipt(
                41,
                f"https://bitbucket.org/{intent.context.workspace}/{intent.context.repository_slug}/pull-requests/41",
                self.state,
                intent.context.repository_id,
                intent.context.source_branch,
                "d" * 40 if self.fault == "race" and self.reads > 1 else self.source,
                intent.target_branch,
                "e" * 40,
            ),
        )

    async def read_pr_merge_status(self, session, **kwargs):
        return self.merge_status

    async def read_rebase_file(self, session, **kwargs):
        with self.factory() as other:
            original = load_change_set_bundle(other, self.identity).group.prepared.files[0]
        return original.original_bytes

    async def verify_commit_files(self, session, *, intent, commit):
        assert commit == self.source
        assert intent.branch.parent == "e" * 40
        with self.factory() as other:
            original = load_change_set_bundle(other, self.identity).group.prepared.files[0]
        assert intent.files[0].content == original.content
        self.verified += 1
        if self.fault == "content":
            raise _WireError("conflict", "written_file_mismatch")


def run_check(accepted, remote):
    ready, group_id = accepted
    with ready[2]() as session:
        attempt = session.get(ChangeSet, group_id).attempt
    action(accepted, request_reconcile, expected_attempt=attempt, enqueuer=lambda _: None)
    asyncio.run(
        submission_jobs.recover_change_set(
            ready[2],
            change_set_id=group_id,
            reads=PreparedSource(ready[1]),
            writes=remote,
        )
    )


def setup_remote(accepted):
    ready, group_id = accepted
    remote = TrackingRemote(ready[2], group_id)
    asyncio.run(
        submission_jobs.execute_change_set(
            ready[2],
            change_set_id=group_id,
            reads=PreparedSource(ready[1]),
            writes=remote,
        )
    )
    return remote


def test_verified_rebase_preserves_original_evidence_and_repeat_check_is_read_only(accepted):
    ready, group_id = accepted
    remote = setup_remote(accepted)
    with ready[2]() as session:
        original = session.get(ChangeSet, group_id).original_prepared_payload
    for _ in range(2):
        run_check(accepted, remote)
        with ready[2]() as session:
            row = session.get(ChangeSet, group_id)
            assert row.status == "succeeded" and row.error_code is None
            assert row.commit_hash == "b" * 40
            assert row.original_prepared_payload == original
            assert row.pr_tracking["source_commit"] == "c" * 40
            assert row.pr_tracking["content_status"] == "verified"
            assert not effect_summary(session, row).unresolved
            assert session.scalars(select(ChangeSetFile)).one().active_claim
    assert remote.calls == ["branch", "commit", "pull_request"]
    with ready[2]() as session:
        receipts = list(
            session.scalars(
                select(ChangeSetEvent).where(
                    ChangeSetEvent.event_kind == "observation",
                    ChangeSetEvent.step == "pull_request",
                )
            )
        )
        assert len(receipts) == 1 and receipts[0].receipt["source_commit"] == "b" * 40


@pytest.mark.parametrize(
    "fault,merge,error",
    [
        (None, "conflicts", "pr_merge_conflicts"),
        (None, "unknown", "pr_check_unavailable"),
        ("content", "clean", "pr_content_changed"),
        ("race", "clean", "pr_changed_during_check"),
        ("unavailable", "clean", "pr_check_unavailable"),
    ],
)
def test_unsafe_or_unavailable_checks_never_look_successful(accepted, fault, merge, error):
    ready, group_id = accepted
    remote = setup_remote(accepted)
    remote.fault, remote.merge_status = fault, merge
    run_check(accepted, remote)
    with ready[2]() as session:
        row = session.get(ChangeSet, group_id)
        assert row.status == "needs_attention" and row.error_code == error
        assert not effect_summary(session, row).unresolved
        assert row.commit_hash == "b" * 40
        assert session.scalars(select(ChangeSetFile)).one().active_claim
    assert remote.calls == ["branch", "commit", "pull_request"]


def test_original_head_can_have_real_merge_conflicts(accepted):
    ready, group_id = accepted
    remote = setup_remote(accepted)
    remote.source, remote.merge_status = "b" * 40, "conflicts"
    run_check(accepted, remote)
    with ready[2]() as session:
        row = session.get(ChangeSet, group_id)
        assert row.error_code == "pr_merge_conflicts"
        assert row.pr_tracking["content_status"] == "original"
    assert remote.verified == 0


@pytest.mark.parametrize("state", ["MERGED", "DECLINED", "SUPERSEDED"])
def test_closed_rebased_pr_releases_claims_without_reading_deleted_branch(accepted, state):
    ready, group_id = accepted
    remote = setup_remote(accepted)
    remote.state = state
    run_check(accepted, remote)
    with ready[2]() as session:
        row = session.get(ChangeSet, group_id)
        assert row.status == "resolved" and row.pr_state == state
        assert row.claims_released_at is not None
        assert not session.scalars(select(ChangeSetFile)).one().active_claim
    assert remote.verified == 0
