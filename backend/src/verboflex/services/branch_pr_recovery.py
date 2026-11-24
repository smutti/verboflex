"""Read-only proof for a duplicate PR request after a previously merged review."""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.integrations.bitbucket.writes import (
    BitbucketWriteAdapter,
    PullRequestIntent,
    PullRequestReceipt,
)
from verboflex.localization.importing.core import (
    MAX_CANONICAL_AGGREGATE_BYTES,
    MAX_CANONICAL_FILE_BYTES,
)
from verboflex.models.branch_workflow import BranchJob, BranchWorkflow
from verboflex.services.approval_target import contains_approved_values
from verboflex.services.branch_jobs import _intent
from verboflex.services.submission_codec import decode_approval_snapshot
from verboflex.services.submission_selection import (
    SubmissionReadAdapter,
    provider_repository_identity,
)
from verboflex.services.writeback_authority import CapturedWritebackAuthority


async def integrated_review(
    factory: sessionmaker[Session],
    workflow: BranchWorkflow,
    job: BranchJob,
    intent: PullRequestIntent,
    reads: SubmissionReadAdapter,
    writes: BitbucketWriteAdapter,
) -> tuple[PullRequestReceipt, str] | None:
    """Require the original marked PR, equal live heads and all intervening approvals."""
    ctx = intent.context
    repo = {"workspace": ctx.workspace, "repository_slug": ctx.repository_slug}
    with factory() as session:
        prior = session.scalar(
            select(BranchJob)
            .where(
                BranchJob.workflow_id == workflow.id,
                BranchJob.kind == "pull_request",
                BranchJob.state == "merged",
                BranchJob.sequence < job.sequence,
                BranchJob.integrated_target_hash.is_(None),
            )
            .order_by(BranchJob.sequence.desc())
            .limit(1)
        )
        if (
            prior is None
            or prior.commit_hash != intent.source_commit
            or prior.pr_id is None
            or not prior.intent
        ):
            return None
        original = _intent(workflow, prior)
        if (
            not isinstance(original, PullRequestIntent)
            or original.context.repository_id != ctx.repository_id
        ):
            return None
        prior_id, start = prior.pr_id, prior.sequence
    if await provider_repository_identity(factory, adapter=reads, **repo) != ctx.repository_id:
        return None
    with factory() as session:
        outcome = await writes.read_pull_request(
            session, intent=original, pull_request_id=prior_id, allow_rebased=True
        )
    receipt = outcome.receipt
    if (
        outcome.state != "verified"
        or receipt is None
        or receipt.state != "MERGED"
        or receipt.source_commit != intent.source_commit
    ):
        return None

    async def common_head() -> str | None:
        with factory() as session:
            source = await reads.resolve_repository_branch(
                session, branch=workflow.work_branch, **repo
            )
            target = await reads.resolve_repository_branch(
                session, branch=workflow.target_branch, **repo
            )
        if source.name != workflow.work_branch or target.name != workflow.target_branch:
            return None
        return target.commit_hash if source.commit_hash == target.commit_hash else None

    head = await common_head()
    if head is None:
        return None
    files: dict[str, bytes] = {}
    total = 0
    with factory() as session:
        rows = session.scalars(
            select(BranchJob)
            .where(
                BranchJob.workflow_id == workflow.id,
                BranchJob.sequence > start,
                BranchJob.sequence < job.sequence,
            )
            .order_by(BranchJob.sequence)
            .execution_options(yield_per=1)
        )
        for row in rows:
            if row.kind != "commit" or row.state != "committed" or not row.authority:
                return None
            captured = decode_approval_snapshot(row.authority)
            if not isinstance(captured, CapturedWritebackAuthority) or not captured.files:
                return None
            for file in captured.files:
                ref = file.authority
                if ref.repository_id != workflow.repository_id or ref.repository_side == "keys":
                    return None
                if ref.path not in files:
                    with factory() as provider_session:
                        meta = await reads.read_repository_source_metadata(
                            provider_session, commit_hash=head, path=ref.path, **repo
                        )
                        total += meta.size_bytes
                        if (
                            meta.attributes != ()
                            or meta.path != ref.path
                            or meta.commit_hash != head
                            or meta.size_bytes > MAX_CANONICAL_FILE_BYTES
                            or total > MAX_CANONICAL_AGGREGATE_BYTES
                        ):
                            return None
                        content = await reads.read_repository_source_file(
                            provider_session,
                            commit_hash=head,
                            path=ref.path,
                            max_bytes=max(1, meta.size_bytes),
                            **repo,
                        )
                    if len(content) != meta.size_bytes:
                        return None
                    files[ref.path] = content
                if not contains_approved_values(file, files[ref.path]):
                    return None
    if await common_head() != head:
        return None
    return receipt, head
