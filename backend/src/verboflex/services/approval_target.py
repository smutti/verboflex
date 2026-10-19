"""Read-only verification of approved values on the configured PR destination.

Called only by Celery. A merged PR or a working-branch receipt is not evidence
that the current approved text is present on the target branch.
"""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from verboflex.integrations.bitbucket.client import BitbucketProviderReadError
from verboflex.localization.importing.core import (
    MAX_CANONICAL_AGGREGATE_BYTES,
    MAX_CANONICAL_FILE_BYTES,
    canonical_selector_bytes,
)
from verboflex.localization.writing.parsing import inspect_writeback_snapshot
from verboflex.models.branch_workflow import BranchJob, BranchWorkflow
from verboflex.models.product import Product
from verboflex.models.repository import Repository
from verboflex.models.review import ReviewActivity, TranslationProposal
from verboflex.services.branch_jobs import LEASE
from verboflex.services.branch_workflow import active_mapping
from verboflex.services.submission_codec import decode_approval_snapshot
from verboflex.services.submission_selection import (
    SubmissionReadAdapter,
    provider_repository_identity,
)
from verboflex.services.writeback_authority import CapturedFile, CapturedWritebackAuthority


def contains_approved_values(file: CapturedFile, content: bytes) -> bool:
    parsed = inspect_writeback_snapshot(replace(file.parser_input, content=content))
    if parsed.issues or not file.edits:
        return False
    values: dict[tuple[str, str, bytes], list[str]] = {}
    positions: dict[str, set[int]] = {}
    for value in parsed.values:
        identity = value.logical_key, value.language, canonical_selector_bytes(value.selector)
        values.setdefault(identity, []).append(value.display_text)
        positions.setdefault(value.logical_key, set()).add(value.locator.position)
    return all(
        values.get((edit.logical_key, edit.language, canonical_selector_bytes(edit.selector)))
        == [edit.replacement_text]
        and (file.parser_input.format != "android_xml" or len(positions[edit.logical_key]) == 1)
        for edit in file.edits
    )


def current_approval(session: Session, job: BranchJob) -> TranslationProposal | None:
    return session.scalar(
        select(TranslationProposal)
        .join(ReviewActivity, ReviewActivity.proposal_id == TranslationProposal.id)
        .where(
            ReviewActivity.id == job.activity_id,
            ReviewActivity.proposal_version == TranslationProposal.version,
            TranslationProposal.state == "approved",
        )
    )


async def refresh_approval_target(
    factory: sessionmaker[Session], *, job_id: UUID, reads: SubmissionReadAdapter
) -> None:
    owner, now = uuid4(), datetime.now(UTC)
    with factory.begin() as session:
        job = session.scalar(select(BranchJob).where(BranchJob.id == job_id).with_for_update())
        if (
            job is None
            or job.state != "committed"
            or job.kind != "commit"
            or (job.owner is not None and job.updated_at > now - LEASE)
        ):
            return
        proposal = current_approval(session, job)
        workflow = session.get_one(BranchWorkflow, job.workflow_id)
        product = session.get_one(Product, workflow.product_id)
        job.updated_at = now
        if (
            proposal is None
            or not product.is_active
            or product.deleted_at is not None
            or active_mapping(session, workflow) is None
            or job.authority is None
            or job.intent is None
        ):
            return
        captured = decode_approval_snapshot(job.authority)
        if (
            not isinstance(captured, CapturedWritebackAuthority)
            or not captured.files
            or not any(
                p.proposal_id == proposal.id and p.version == proposal.version
                for p in captured.proposals
            )
        ):
            return
        repository = session.get_one(Repository, workflow.repository_id)
        workspace, slug = repository.workspace, repository.repository_slug
        target, provider_id = workflow.target_branch, str(job.intent["provider_id"])
        proposal_id, version = proposal.id, proposal.version
        job.owner = owner

    # Failure leaves the last verified observation intact. It never changes the
    # commit job to blocked, writes to Git, or triggers another approval/PR.
    try:
        identity = await provider_repository_identity(
            factory, workspace=workspace, repository_slug=slug, adapter=reads
        )
        if str(identity) != provider_id:
            return
        with factory() as session:
            head = await reads.resolve_repository_branch(
                session, workspace=workspace, repository_slug=slug, branch=target
            )
        if head.name != target:
            return
        integrated, total = True, 0
        for file in captured.files:
            if (
                file.authority.repository_id != workflow.repository_id
                or file.authority.repository_side == "keys"
            ):
                return
            try:
                with factory() as session:
                    metadata = await reads.read_repository_source_metadata(
                        session,
                        workspace=workspace,
                        repository_slug=slug,
                        commit_hash=head.commit_hash,
                        path=file.authority.path,
                    )
                    total += metadata.size_bytes
                    if (
                        metadata.path != file.authority.path
                        or metadata.commit_hash != head.commit_hash
                        or metadata.attributes != ()
                        or metadata.size_bytes > MAX_CANONICAL_FILE_BYTES
                        or total > MAX_CANONICAL_AGGREGATE_BYTES
                    ):
                        return
                    content = await reads.read_repository_source_file(
                        session,
                        workspace=workspace,
                        repository_slug=slug,
                        commit_hash=head.commit_hash,
                        path=file.authority.path,
                        max_bytes=max(1, metadata.size_bytes),
                    )
            except BitbucketProviderReadError as error:
                if error.kind != "not_found":
                    raise
                integrated = False
                break
            if len(content) != metadata.size_bytes:
                return
            integrated = integrated and contains_approved_values(file, content)
        with factory.begin() as session:
            job = session.get_one(BranchJob, job_id, with_for_update=True)
            proposal = session.get(TranslationProposal, proposal_id, with_for_update=True)
            if (
                job.owner == owner
                and proposal is not None
                and proposal.version == version
                and proposal.state == "approved"
            ):
                verified_commit = head.commit_hash if integrated else None
                if (proposal.target_branch, proposal.target_commit_hash) != (
                    target,
                    verified_commit,
                ):
                    session.execute(
                        update(TranslationProposal)
                        .where(TranslationProposal.id == proposal_id)
                        .values(
                            target_branch=target,
                            target_commit_hash=verified_commit,
                            updated_at=proposal.updated_at,
                        )
                    )
    except BitbucketProviderReadError:
        return
    finally:
        with factory.begin() as session:
            job = session.get_one(BranchJob, job_id, with_for_update=True)
            if job.owner == owner:
                job.owner, job.updated_at = None, datetime.now(UTC)
