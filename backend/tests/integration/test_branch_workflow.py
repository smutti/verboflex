"""Approval snapshots survive later edits; only explicit PR requests publish a PR."""

# ruff: noqa: F811

import asyncio
import hashlib

import pytest
from sqlalchemy import select

from tests.integration.test_preview_jobs import (  # noqa: F401
    clean_preview_database,
    preview_session_factory,
)
from tests.integration.test_writeback_authority import PreparedSource, seed_writeback_authority
from verboflex.auth.principal import Principal
from verboflex.integrations.bitbucket.client import BitbucketBranch, BitbucketSourceMetadata
from verboflex.integrations.bitbucket.writes import CommitReceipt, PullRequestReceipt, WriteOutcome
from verboflex.models.branch_workflow import BranchJob
from verboflex.models.review import TranslationProposal
from verboflex.models.user import User
from verboflex.schemas.users import RoleName
from verboflex.services.branch_jobs import execute_branch_job
from verboflex.services.branch_workflow import (
    BranchWorkflowError,
    configure,
    request_pr,
    retry_job,
)
from verboflex.services.translation_reviews import (
    ProposalValueInput,
    save_translation_proposal,
    transition_translation_proposal,
)


class Remote(PreparedSource):
    def __init__(self, seed, factory):
        super().__init__(seed)
        self.factory = factory
        self.head = "a" * 40
        self.versions = {self.head: dict(seed.adapter.files)}
        self.commits = []
        self.prs = []
        self.uncertain = False
        self.before = lambda: None

    async def resolve_repository_branch(self, session, **kw):
        return BitbucketBranch(
            kw["branch"], self.head if kw["branch"] == "feature/translations" else "a" * 40
        )

    async def read_repository_source_metadata(self, session, **kw):
        content = self.versions[kw["commit_hash"]][kw["path"]]
        return BitbucketSourceMetadata(kw["path"], kw["commit_hash"], len(content), ())

    async def read_repository_source_file(self, session, **kw):
        return self.versions[kw["commit_hash"]][kw["path"]]

    async def create_commit(self, session, *, intent, before_send):
        self.before()
        if not before_send():
            return WriteOutcome("not_sent", "authority_changed")
        with self.factory() as other:
            job = other.get(BranchJob, intent.branch.context.change_set_id)
            assert job.state == "sending" and job.intent is not None
        assert intent.branch.parent == self.head
        assert intent.branch.context.source_branch == "feature/translations"
        assert all(
            hashlib.sha256(self.versions[self.head][f.path]).hexdigest() == f.before_sha256
            for f in intent.files
        )
        current = dict(self.versions[self.head])
        current.update({f.path: f.content for f in intent.files})
        self.head = hashlib.sha1(str(len(self.commits)).encode()).hexdigest()
        self.versions[self.head] = current
        self.commits.append(intent)
        if self.uncertain:
            return WriteOutcome("unknown", "timeout")
        return await self.reconcile_commit(session, intent=intent)

    async def reconcile_commit(self, session, *, intent):
        assert self.commits[-1] == intent
        return WriteOutcome(
            "verified",
            "commit_verified",
            CommitReceipt(
                self.head,
                intent.branch.parent,
                intent.branch.context.source_branch,
                intent.manifest_digest,
            ),
        )

    async def create_pull_request(self, session, *, intent, before_send):
        assert before_send()
        assert intent.context.source_branch == "feature/translations"
        assert intent.target_branch == "main"
        self.prs.append(intent)
        return WriteOutcome(
            "verified",
            "pull_request_verified",
            PullRequestReceipt(
                1,
                "https://bitbucket.org/preview-team/preview-repository/pull-requests/1",
                "OPEN",
                intent.context.repository_id,
                intent.context.source_branch,
                intent.source_commit,
                intent.target_branch,
                intent.target_head,
            ),
        )


def setup(factory, monkeypatch):
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as s:
        configure(
            s,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            mapping_id=seed.mapping_id,
            work_branch="feature/translations",
            target_branch="main",
        )
    return seed, Remote(seed, factory)


def approve(factory, seed, text):
    principal = Principal(seed.actor_id, "writer@example.test", "Writer", (RoleName.ADMIN,), False)
    with factory.begin() as s:
        p = s.get(TranslationProposal, seed.proposal_id)
        from verboflex.models.translation import TranslationValueRevision

        revisions = {
            v.translation_value_id: s.scalar(
                select(TranslationValueRevision)
                .where(
                    TranslationValueRevision.value_id == v.translation_value_id,
                )
                .order_by(TranslationValueRevision.revision_number.desc())
                .limit(1)
            )
            for v in p.values
        }
        inputs = [
            ProposalValueInput(
                v.translation_value_id,
                v.selector_version,
                v.selector_digest,
                revisions[v.translation_value_id].revision_number,
                revisions[v.translation_value_id].revision_digest,
                text,
            )
            for v in p.values
        ]
        saved = save_translation_proposal(
            s,
            principal=principal,
            translation_group_id=seed.value_ids[0],
            values=inputs,
            expected_version=p.version,
        )
        transition_translation_proposal(
            s,
            principal=principal,
            translation_group_id=seed.value_ids[0],
            target_state="approved",
            expected_version=saved.version,
            reason=None,
        )
        return s.scalar(select(BranchJob.id).order_by(BranchJob.sequence.desc()).limit(1))


def run(factory, remote, job_id):
    asyncio.run(execute_branch_job(factory, job_id=job_id, reads=remote, writes=remote))
    with factory() as s:
        job = s.get(BranchJob, job_id)
        return job.state, job.error_code


def test_each_approval_commits_in_order_and_pr_is_explicit(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    first = approve(factory, seed, "Prima")
    second = approve(factory, seed, "Seconda")
    assert run(factory, remote, second)[0] == "queued"
    assert run(factory, remote, first) == ("committed", None)
    assert b"Prima" in remote.versions[remote.head]["app/res/values-it/strings.xml"]
    assert run(factory, remote, second) == ("committed", None)
    assert b"Seconda" in remote.versions[remote.head]["app/res/values-it/strings.xml"]
    assert len(remote.commits) == 2 and remote.prs == []
    assert remote.commits[1].branch.parent != "a" * 40
    run(factory, remote, first)
    assert len(remote.commits) == 2
    with factory.begin() as s:
        pr = request_pr(s, product_id=seed.product_id, actor_id=seed.actor_id).id
    assert run(factory, remote, pr) == ("open", None)
    with factory.begin() as s:
        assert request_pr(s, product_id=seed.product_id, actor_id=seed.actor_id).id == pr
    assert len(remote.prs) == 1


def test_timeout_recovers_same_commit_without_resending(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    first = approve(factory, seed, "Prima")
    second = approve(factory, seed, "Seconda")
    remote.uncertain = True
    assert run(factory, remote, first) == ("blocked", "timeout")
    assert run(factory, remote, second)[0] == "queued"
    with factory.begin() as s:
        with pytest.raises(BranchWorkflowError):
            request_pr(s, product_id=seed.product_id, actor_id=seed.actor_id)
        retry_job(s, product_id=seed.product_id, actor_id=seed.actor_id, job_id=first)
    assert run(factory, remote, first) == ("committed", None)
    assert len(remote.commits) == 1


def test_external_file_edit_is_never_overwritten(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    job = approve(factory, seed, "Nuova")
    remote.head = "b" * 40
    remote.versions[remote.head] = dict(remote.versions["a" * 40])
    remote.versions[remote.head]["app/res/values-it/strings.xml"] += b"\n<!-- external change -->"
    assert run(factory, remote, job) == ("blocked", "file_changed")
    assert not remote.commits


def test_permission_loss_immediately_before_send_blocks_commit(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    job = approve(factory, seed, "Nuova")

    def revoke():
        with factory.begin() as s:
            s.get(User, seed.actor_id).is_active = False

    remote.before = revoke
    assert run(factory, remote, job) == ("blocked", "authority_changed")
    assert not remote.commits


def test_new_translation_approval_also_creates_a_commit(preview_session_factory, monkeypatch):
    from uuid import uuid4

    from tests.integration.test_translation_authoring import draft
    from verboflex.services import translation_authoring as authoring

    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    data = draft(factory, seed)
    with factory.begin() as s:
        saved = authoring.save(
            s, product_id=seed.product_id, actor_id=seed.actor_id, request_id=uuid4(), data=data
        )
        authoring.transition(
            s,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=saved.id,
            expected_version=saved.version,
            state="approved",
        )
        job_id = s.scalar(select(BranchJob.id).order_by(BranchJob.sequence.desc()).limit(1))
    assert run(factory, remote, job_id) == ("committed", None)
    assert b"new_key" in remote.versions[remote.head]["app/res/values-it/strings.xml"]
    assert not remote.prs


def test_refreshed_import_of_merged_file_allows_next_approval(preview_session_factory, monkeypatch):
    from tests.integration.test_writeback_authority import _run

    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    first = approve(factory, seed, "Prima")
    assert run(factory, remote, first) == ("committed", None)
    # The import branch now contains exactly the file committed and merged earlier.
    seed.adapter.files = dict(remote.versions[remote.head])
    seed.adapter.commit_hashes = ["b" * 40]
    remote.versions["b" * 40] = dict(seed.adapter.files)
    refreshed = _run(factory, seed.product_id, seed.mapping_id)
    assert refreshed.state == "current"
    second = approve(factory, seed, "Dopo merge")
    assert run(factory, remote, second) == ("committed", None)
    assert b"Dopo merge" in remote.versions[remote.head]["app/res/values-it/strings.xml"]
