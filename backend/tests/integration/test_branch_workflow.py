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
    def __init__(self, seed, factory, *, work_branch="feature/translations", target_branch="main"):
        super().__init__(seed)
        self.factory = factory
        self.head = "a" * 40
        self.versions = {self.head: dict(seed.adapter.files)}
        self.commits = []
        self.prs = []
        self.uncertain = False
        self.uncertain_pr = False
        self.before = lambda: None
        self.work_branch, self.target_branch = work_branch, target_branch

    async def resolve_repository_branch(self, session, **kw):
        return BitbucketBranch(
            kw["branch"], self.head if kw["branch"] == self.work_branch else "a" * 40
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
        assert intent.branch.context.source_branch == self.work_branch
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
        assert intent.context.source_branch == self.work_branch
        assert intent.target_branch == self.target_branch
        self.prs.append(intent)
        if self.uncertain_pr:
            return WriteOutcome("unknown", "timeout")
        return await self.reconcile_pull_request(session, intent=intent)

    async def reconcile_pull_request(self, session, *, intent):
        assert self.prs[-1] == intent
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


def setup(factory, monkeypatch, *, work_branch="feature/translations", target_branch="main"):
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as s:
        configure(
            s,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            mapping_id=seed.mapping_id,
            work_branch=work_branch,
            target_branch=target_branch,
        )
    return seed, Remote(seed, factory, work_branch=work_branch, target_branch=target_branch)


def save_draft(factory, seed, text):
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
        return saved.version


def approve(factory, seed, text):
    version = save_draft(factory, seed, text)
    principal = Principal(seed.actor_id, "writer@example.test", "Writer", (RoleName.ADMIN,), False)
    with factory.begin() as s:
        transition_translation_proposal(
            s,
            principal=principal,
            translation_group_id=seed.value_ids[0],
            target_state="approved",
            expected_version=version,
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


def test_concurrent_approval_requests_queue_exactly_one_commit(
    preview_session_factory, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from verboflex.services.translation_reviews import ProposalVersionConflict

    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    version = save_draft(factory, seed, "Only once")
    principal = Principal(seed.actor_id, "writer@example.test", "Writer", (RoleName.ADMIN,), False)
    barrier = Barrier(2)

    def accept():
        barrier.wait(timeout=10)
        try:
            with factory.begin() as session:
                transition_translation_proposal(
                    session,
                    principal=principal,
                    translation_group_id=seed.value_ids[0],
                    target_state="approved",
                    expected_version=version,
                    reason=None,
                )
            return "approved"
        except ProposalVersionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept(), range(2)))
    assert sorted(results) == ["approved", "conflict"]
    with factory() as session:
        job = session.scalars(select(BranchJob.id)).one()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: run(factory, remote, job), range(2)))
    assert run(factory, remote, job)[0] == "committed"
    assert len(remote.commits) == 1 and not remote.prs


def test_worker_crash_after_commit_recovers_without_another_post(
    preview_session_factory, monkeypatch
):
    from datetime import UTC, datetime, timedelta

    class WorkerLost(BaseException):
        pass

    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    job_id = approve(factory, seed, "Survives crash")
    original = remote.create_commit

    async def crash(*args, **kwargs):
        await original(*args, **kwargs)
        raise WorkerLost()

    remote.create_commit = crash
    with pytest.raises(WorkerLost):
        run(factory, remote, job_id)
    with factory.begin() as session:
        job = session.get_one(BranchJob, job_id)
        assert job.state == "sending"
        job.updated_at = datetime.now(UTC) - timedelta(minutes=11)
    assert run(factory, remote, job_id) == ("committed", None)
    assert len(remote.commits) == 1 and not remote.prs


def test_explicit_pr_timeout_reconciles_immediately_without_duplicates(
    preview_session_factory, monkeypatch
):
    from verboflex.worker.branch_tasks import dispatchable_jobs

    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    job = approve(factory, seed, "Ready")
    run(factory, remote, job)
    assert not remote.prs
    with factory.begin() as session:
        pr = request_pr(session, product_id=seed.product_id, actor_id=seed.actor_id).id
    remote.uncertain_pr = True
    assert run(factory, remote, pr) == ("blocked", "timeout")
    with factory.begin() as session:
        retry_job(session, product_id=seed.product_id, actor_id=seed.actor_id, job_id=pr)
    with factory() as session:
        assert pr in dispatchable_jobs(session)
    assert run(factory, remote, pr) == ("open", None)
    assert len(remote.prs) == 1 and len(remote.commits) == 1


def test_blocked_backlog_does_not_starve_another_product(preview_session_factory, monkeypatch):
    from verboflex.worker.branch_tasks import dispatchable_jobs

    factory = preview_session_factory
    seed, _ = setup(factory, monkeypatch)
    first = approve(factory, seed, "Blocked")
    with factory.begin() as session:
        job = session.get_one(BranchJob, first)
        job.state = "blocked"
        for _ in range(110):
            session.add(
                BranchJob(
                    workflow_id=job.workflow_id,
                    actor_id=seed.actor_id,
                    membership=job.membership,
                    kind="commit",
                    label="Waiting",
                    state="queued",
                )
            )
    second, remote = setup(factory, monkeypatch)
    ready = approve(factory, second, "Other product")
    with factory() as session:
        assert dispatchable_jobs(session) == [ready]
    assert run(factory, remote, ready)[0] == "committed"


def test_new_translation_cannot_be_approved_twice_without_changes(
    preview_session_factory, monkeypatch
):
    from uuid import uuid4

    from tests.integration.test_translation_authoring import draft
    from verboflex.services import translation_authoring as authoring

    factory = preview_session_factory
    seed, _ = setup(factory, monkeypatch)
    data = draft(factory, seed)
    with factory.begin() as session:
        saved = authoring.save(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=uuid4(),
            data=data,
        )
        approved = authoring.transition(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            request_id=saved.id,
            expected_version=saved.version,
            state="approved",
        )
    for version in (saved.version, approved.version):
        with pytest.raises(authoring.AuthoringError), factory.begin() as session:
            authoring.transition(
                session,
                product_id=seed.product_id,
                actor_id=seed.actor_id,
                request_id=saved.id,
                expected_version=version,
                state="approved",
            )
    with factory() as session:
        assert len(list(session.scalars(select(BranchJob)))) == 1


def test_long_repository_path_fits_durable_file_index(preview_session_factory, monkeypatch):
    from uuid import uuid4

    from verboflex.models.branch_workflow import BranchFile
    from verboflex.services.branch_jobs import _branch_file
    from verboflex.services.branch_workflow import workflow_for

    factory = preview_session_factory
    seed, _ = setup(factory, monkeypatch)
    path = "/".join(uuid4().hex for _ in range(120)) + "/strings.xml"
    assert 3000 < len(path) < 4096
    with factory.begin() as session:
        workflow = workflow_for(session, seed.product_id)
        workflow_id = workflow.id
        session.add(
            BranchFile(
                workflow_id=workflow_id,
                path=path,
                baseline_sha256="a" * 64,
                content_sha256="b" * 64,
                edits=b"fixture",
            )
        )
    with factory() as session:
        assert _branch_file(session, workflow_id, path).path == path


def test_migration_preserves_existing_workflow_and_committed_files(
    preview_session_factory, monkeypatch
):
    from pathlib import Path

    from alembic.config import Config

    from alembic import command
    from verboflex.models.branch_workflow import BranchFile

    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    first = approve(factory, seed, "Before migration")
    assert run(factory, remote, first)[0] == "committed"
    with factory() as session:
        row = session.scalars(select(BranchFile)).one()
        expected = (row.workflow_id, row.path, row.content_sha256, row.edits)
    config = Config(Path(__file__).resolve().parents[2] / "alembic.ini")
    monkeypatch.setenv("VERBOFLEX_DATABASE_URL", str(factory.kw["bind"].url))
    command.downgrade(config, "0047_branch_workflow")
    command.upgrade(config, "head")
    with factory() as session:
        row = session.scalars(select(BranchFile)).one()
        assert (row.workflow_id, row.path, row.content_sha256, row.edits) == expected
    second = approve(factory, seed, "After migration")
    assert run(factory, remote, second)[0] == "committed"
    assert len(remote.commits) == 2


def republish(factory, seed, *, extra_mapping=False, source_branch=None):
    """Publish fresh mapping UUIDs through actual preview/confirmation, then import."""
    from uuid import UUID, uuid4

    from tests.integration.test_writeback_authority import _run
    from verboflex.models.product import Product, ProductRevision
    from verboflex.models.product_mapping import (
        ProductMappingAllowedTarget,
        ProductMappingRepositorySide,
        ProductRepositoryMapping,
    )
    from verboflex.models.repository import Repository
    from verboflex.services import preview_jobs
    from verboflex.services.products import save_product_candidate
    from verboflex.services.publication import publish_product_candidate
    from verboflex.worker.preview_tasks import process_preview

    with factory() as s:
        p = s.get_one(Product, seed.product_id)
        name, version = p.display_name, s.get_one(ProductRevision, p.active_revision_id).version
    with factory() as s:
        p = save_product_candidate(
            s,
            actor_id=seed.actor_id,
            product_id=seed.product_id,
            expected_version=version,
            name=name,
            description="Updated configuration",
        )
        revision_id = p.candidate_revision_id
    with factory.begin() as s:
        mapping = s.scalars(
            select(ProductRepositoryMapping).where(
                ProductRepositoryMapping.revision_id == revision_id
            )
        ).one()
        ids = [mapping.id]
        if source_branch is not None:
            from verboflex.services.mappings import _direct_identity

            mapping.sides[0].source_branch = source_branch
            mapping.identity_key = _direct_identity(mapping.sides[0].repository_id, source_branch)
        if extra_mapping:
            repo = Repository(id=uuid4(), workspace="preview-team", repository_slug="second-repo")
            s.add(repo)
            s.flush()
            second = ProductRepositoryMapping(
                id=uuid4(),
                revision_id=revision_id,
                topology="direct",
                identity_key=f'["direct","{repo.id}","main"]',
                sides=[
                    ProductMappingRepositorySide(
                        role="direct", repository_id=repo.id, source_branch="main"
                    )
                ],
                allowed_targets=[ProductMappingAllowedTarget(branch="main", is_default=True)],
            )
            s.add(second)
            ids.append(second.id)
    for mapping_id in ids:
        with factory() as s:
            version = s.get_one(ProductRevision, revision_id).version
        with factory() as s:
            job = preview_jobs.create_or_reuse_preview_job(
                s,
                product_id=seed.product_id,
                mapping_id=mapping_id,
                expected_candidate_version=version,
                commits={"direct": "a" * 40},
                enqueuer=lambda _: None,
                actor_id=seed.actor_id,
            )
        preview_jobs.execute_preview_job(
            factory,
            job_id=job.id,
            processor=lambda identity: process_preview(
                identity, factory=factory, adapter=seed.adapter
            ),
        )
        with factory() as s:
            completed = preview_jobs.get_preview_job(s, job_id=job.id)
            assert completed.state == "succeeded"
            candidate = completed.result["layout_candidates"][0]
        with factory() as s:
            preview_jobs.confirm_preview_job(
                s,
                job_id=job.id,
                preview_digest=completed.result["digest"],
                layout_candidate_id=UUID(candidate["id"]),
                layout_candidate_version=1,
                base_language="en",
                actor_id=seed.actor_id,
            )
    with factory() as s:
        version = s.get_one(ProductRevision, revision_id).version
    with factory() as s:
        publish_product_candidate(
            s,
            product_id=seed.product_id,
            candidate_revision_id=revision_id,
            expected_candidate_version=version,
            actor_id=seed.actor_id,
        )
    for mapping_id in ids:
        assert _run(factory, seed.product_id, mapping_id).state == "current"
    return ids


def test_republished_equivalent_mapping_keeps_committing_on_same_workflow(
    preview_session_factory, monkeypatch
):
    from verboflex.services.branch_workflow import workflow_for

    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    first = approve(factory, seed, "Before publication")
    run(factory, remote, first)
    mapping_id = republish(factory, seed)[0]
    assert mapping_id != seed.mapping_id
    with factory.begin() as s:
        existing = workflow_for(s, seed.product_id)
        reused = configure(
            s,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            mapping_id=mapping_id,
            work_branch="feature/translations",
            target_branch="main",
        )
        assert existing.id == reused.id
    second = approve(factory, seed, "After publication")
    assert run(factory, remote, second) == ("committed", None)
    assert len(remote.commits) == 2


def test_multiple_translation_sources_have_separate_branch_queues(
    preview_session_factory, monkeypatch
):
    from types import SimpleNamespace

    from verboflex.models.translation import LocalizationScope, TranslationValue

    factory = preview_session_factory
    seed, first_remote = setup(factory, monkeypatch)
    mapping_id, second_mapping_id = republish(factory, seed, extra_mapping=True)
    with factory.begin() as s:
        second_workflow = configure(
            s,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            mapping_id=second_mapping_id,
            work_branch="feature/translations",
            target_branch="main",
        )
        second_workflow_id = second_workflow.id
        values = list(
            s.scalars(
                select(TranslationValue)
                .join(LocalizationScope, LocalizationScope.id == TranslationValue.scope_id)
                .where(
                    LocalizationScope.current_mapping_id == second_mapping_id,
                    TranslationValue.language == "it",
                )
            )
        )
        # Start an ordinary proposal for the newly imported second source.
        proposal = TranslationProposal(
            scope_id=values[0].scope_id,
            translation_key_id=values[0].translation_key_id,
            language="it",
            state="draft",
            version=0,
            created_by=seed.actor_id,
            updated_by=seed.actor_id,
        )
        s.add(proposal)
        s.flush()
        second_seed = SimpleNamespace(
            **{
                **vars(seed),
                "mapping_id": second_mapping_id,
                "proposal_id": proposal.id,
                "value_ids": tuple(v.id for v in values),
            }
        )
    # Use the actual save service to construct the second proposal's complete values.
    from verboflex.models.translation import TranslationValueRevision

    with factory.begin() as s:
        inputs = []
        for value_id in second_seed.value_ids:
            v = s.get_one(TranslationValue, value_id)
            rev = s.scalars(
                select(TranslationValueRevision)
                .where(TranslationValueRevision.value_id == v.id)
                .order_by(TranslationValueRevision.revision_number.desc())
            ).first()
            inputs.append(
                ProposalValueInput(
                    v.id,
                    v.selector_version,
                    v.selector_digest,
                    rev.revision_number,
                    rev.revision_digest,
                    "Second source",
                )
            )
        save_translation_proposal(
            s,
            principal=Principal(
                seed.actor_id, "writer@example.test", "Writer", (RoleName.ADMIN,), False
            ),
            translation_group_id=second_seed.value_ids[0],
            values=inputs,
            expected_version=0,
        )
    first_job = approve(factory, seed, "First source")
    second_job = approve(factory, second_seed, "Second source")
    second_remote = Remote(second_seed, factory)
    assert run(factory, second_remote, second_job)[0] == "committed"
    assert run(factory, first_remote, first_job)[0] == "committed"
    with factory() as s:
        assert s.get_one(BranchJob, second_job).workflow_id == second_workflow_id
        assert s.get_one(BranchJob, first_job).workflow_id != second_workflow_id
    assert len(second_remote.commits) == len(first_remote.commits) == 1
    assert not first_remote.prs and not second_remote.prs
