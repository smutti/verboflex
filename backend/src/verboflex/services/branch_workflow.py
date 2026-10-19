"""Database-only workflow configuration and durable approval outbox."""

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.audit.ledger import record_audit
from verboflex.auth.product_access import current_product_role, membership_stamp
from verboflex.models.branch_workflow import BranchFile, BranchJob, BranchWorkflow
from verboflex.models.product_mapping import ProductMappingRepositorySide, ProductRepositoryMapping
from verboflex.models.repository import Repository
from verboflex.models.review import TranslationProposal
from verboflex.services.submission_codec import encode_approval_snapshot
from verboflex.services.submission_reviews import SubmissionReviewDenied, _product_actor
from verboflex.services.writeback_authority import (
    ProposalSelection,
    WritebackSelection,
    capture_writeback_authority,
)


class BranchWorkflowError(ValueError):
    pass


def validate_branch(value: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 255
        or value == "@"
        or any(c in value for c in ("..", "@{", "\\", "//"))
        or re.search(r'[\x00-\x20\x7f~^:?*\[\]"]', value)
        or any(not p or p.startswith(".") or p.endswith((".", ".lock")) for p in value.split("/"))
    ):
        raise BranchWorkflowError("Invalid branch name")
    return value


def workflow_for(
    session: Session, product_id: UUID, *, lock: bool = False, workflow_id: UUID | None = None
) -> BranchWorkflow | None:
    query = select(BranchWorkflow).where(BranchWorkflow.product_id == product_id)
    if workflow_id is not None:
        query = query.where(BranchWorkflow.id == workflow_id)
    query = query.order_by(BranchWorkflow.created_at, BranchWorkflow.id).limit(1)
    return session.scalar(query.with_for_update() if lock else query)


def workflow_for_mapping(
    session: Session, product_id: UUID, mapping: ProductRepositoryMapping, *, lock: bool = False
) -> BranchWorkflow | None:
    # Mapping UUIDs change on publication. The repository/import-branch identity is stable.
    query = (
        select(BranchWorkflow)
        .join(ProductRepositoryMapping, ProductRepositoryMapping.id == BranchWorkflow.mapping_id)
        .where(
            BranchWorkflow.product_id == product_id,
            ProductRepositoryMapping.identity_key == mapping.identity_key,
        )
    )
    return session.scalar(query.with_for_update(of=BranchWorkflow) if lock else query)


def active_mapping(session: Session, workflow: BranchWorkflow) -> ProductRepositoryMapping | None:
    from verboflex.models.product import Product

    original = session.get_one(ProductRepositoryMapping, workflow.mapping_id)
    product = session.get_one(Product, workflow.product_id, populate_existing=True)
    return session.scalar(
        select(ProductRepositoryMapping).where(
            ProductRepositoryMapping.revision_id == product.active_revision_id,
            ProductRepositoryMapping.identity_key == original.identity_key,
        )
    )


def configure(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    mapping_id: UUID,
    work_branch: str,
    target_branch: str,
) -> BranchWorkflow:
    product, _ = _product_actor(session, product_id, actor_id, action=True)
    if current_product_role(session, actor_id, product_id) != "admin":
        raise SubmissionReviewDenied("Only an administrator can configure repository branches")
    validate_branch(work_branch)
    validate_branch(target_branch)
    mapping = session.get(ProductRepositoryMapping, mapping_id)
    if mapping is None or mapping.revision_id != product.active_revision_id:
        raise BranchWorkflowError("Select a mapping in the active product configuration")
    side = session.scalar(
        select(ProductMappingRepositorySide).where(
            ProductMappingRepositorySide.mapping_id == mapping_id,
            ProductMappingRepositorySide.role.in_(("direct", "translations")),
        )
    )
    if side is None or work_branch == target_branch:
        raise BranchWorkflowError("The working branch must differ from the PR destination")
    repository = session.get_one(Repository, side.repository_id)
    if repository.provider != "bitbucket":
        raise BranchWorkflowError("Approval commits currently require Bitbucket")
    existing = workflow_for_mapping(session, product_id, mapping)
    if existing:
        if (existing.work_branch, existing.target_branch) == (
            work_branch,
            target_branch,
        ):
            return existing
        raise BranchWorkflowError("This translation source already has an approval commit workflow")
    from verboflex.models.submission import ChangeSet, SubmissionBatch

    outstanding = session.scalar(
        select(ChangeSet.id)
        .join(SubmissionBatch)
        .where(
            SubmissionBatch.product_id == product_id,
            ChangeSet.claims_released_at.is_(None),
        )
        .limit(1)
    )
    if outstanding is not None:
        raise BranchWorkflowError("Finish existing change sets before enabling approval commits")
    # A source-branch correction creates a new mapping identity. Reuse only an
    # inactive, unused workflow in this product; never reinterpret retained jobs.
    reserved = session.scalar(
        select(BranchWorkflow)
        .where(
            BranchWorkflow.repository_id == side.repository_id,
            BranchWorkflow.work_branch == work_branch,
        )
        .with_for_update()
    )
    if reserved is not None:
        if (
            reserved.product_id != product_id
            or reserved.target_branch != target_branch
            or active_mapping(session, reserved) is not None
            or session.scalar(
                select(BranchJob.id).where(BranchJob.workflow_id == reserved.id).limit(1)
            )
            is not None
            or session.scalar(
                select(BranchFile.path).where(BranchFile.workflow_id == reserved.id).limit(1)
            )
            is not None
        ):
            raise BranchWorkflowError("This working branch is already configured")
        reserved.mapping_id = mapping_id
        session.flush()
        record_audit(session, actor_id=actor_id, action="branch.configured", entity_id=reserved.id)
        return reserved
    row = BranchWorkflow(
        product_id=product_id,
        mapping_id=mapping_id,
        repository_id=side.repository_id,
        work_branch=work_branch,
        target_branch=target_branch,
        created_by=actor_id,
    )
    session.add(row)
    session.flush()
    record_audit(session, actor_id=actor_id, action="branch.configured", entity_id=row.id)
    return row


def queue_approval(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    proposal_id: UUID,
    version: int,
    activity_id: UUID,
    label: str,
) -> None:
    if workflow_for(session, product_id) is None:
        return
    captured = capture_writeback_authority(
        session,
        selection=WritebackSelection(actor_id, (ProposalSelection(proposal_id, version),)),
        allow_expired_connection=True,
    )
    if len(captured.mappings) != 1:
        raise BranchWorkflowError("Approve one translation source at a time")
    mapping = session.get_one(ProductRepositoryMapping, captured.mappings[0].mapping_id)
    workflow = workflow_for_mapping(session, product_id, mapping, lock=True)
    if workflow is None:
        raise BranchWorkflowError("Configure approval branches for this translation source first")
    if session.scalar(select(BranchJob.id).where(BranchJob.activity_id == activity_id)):
        return
    proposal = session.get(TranslationProposal, proposal_id)
    if proposal is not None:
        proposal.target_branch, proposal.target_commit_hash = workflow.target_branch, None
    job = BranchJob(
        workflow_id=workflow.id,
        activity_id=activity_id,
        actor_id=actor_id,
        membership=membership_stamp(session, actor_id, product_id),
        kind="commit",
        state="queued",
        label=label[:1024],
        authority=encode_approval_snapshot(captured),
    )
    session.add(job)
    session.flush()
    record_audit(session, actor_id=actor_id, action="branch.approval_queued", entity_id=job.id)


def has_unpublished_commits(session: Session, workflow_id: UUID) -> bool:
    latest = session.scalar(
        select(BranchJob.commit_hash)
        .where(
            BranchJob.workflow_id == workflow_id,
            BranchJob.state == "committed",
        )
        .order_by(BranchJob.sequence.desc())
        .limit(1)
    )
    merged = session.scalar(
        select(BranchJob.commit_hash)
        .where(
            BranchJob.workflow_id == workflow_id,
            BranchJob.state == "merged",
        )
        .order_by(BranchJob.sequence.desc())
        .limit(1)
    )
    return latest is not None and latest != merged


def request_pr(
    session: Session, *, product_id: UUID, actor_id: UUID, workflow_id: UUID | None = None
) -> BranchJob:
    _product_actor(session, product_id, actor_id, action=True)
    if workflow_id is None:
        ids = list(
            session.scalars(
                select(BranchWorkflow.id).where(BranchWorkflow.product_id == product_id).limit(2)
            )
        )
        if len(ids) > 1:
            raise BranchWorkflowError("Select the repository workflow to publish")
    workflow = workflow_for(session, product_id, lock=True, workflow_id=workflow_id)
    if workflow is None:
        raise BranchWorkflowError("Approval commits are not configured")
    if active_mapping(session, workflow) is None:
        raise BranchWorkflowError("This translation source is no longer active")
    pending = session.scalar(
        select(BranchJob.id)
        .where(
            BranchJob.workflow_id == workflow.id,
            BranchJob.state.in_(("queued", "running", "sending", "blocked")),
        )
        .limit(1)
    )
    if pending:
        raise BranchWorkflowError("Wait for all approved changes to be saved on the branch")
    existing = session.scalar(
        select(BranchJob)
        .where(
            BranchJob.workflow_id == workflow.id,
            BranchJob.kind == "pull_request",
            BranchJob.state == "open",
        )
        .order_by(BranchJob.sequence.desc())
        .limit(1)
    )
    if existing:
        return existing
    if not has_unpublished_commits(session, workflow.id):
        raise BranchWorkflowError("There are no new approved commits to publish")
    job = BranchJob(
        workflow_id=workflow.id,
        actor_id=actor_id,
        membership=membership_stamp(session, actor_id, product_id),
        kind="pull_request",
        state="queued",
        label="Pull request",
    )
    session.add(job)
    session.flush()
    record_audit(session, actor_id=actor_id, action="branch.pr_requested", entity_id=job.id)
    return job


def retry_job(session: Session, *, product_id: UUID, actor_id: UUID, job_id: UUID) -> None:
    _product_actor(session, product_id, actor_id, action=True)
    job = session.get(BranchJob, job_id)
    if job is None:
        raise BranchWorkflowError("Change unavailable")
    workflow = workflow_for(session, product_id, lock=True, workflow_id=job.workflow_id)
    if workflow is None:
        raise BranchWorkflowError("Change unavailable")
    if job.state != "blocked":
        raise BranchWorkflowError("This change cannot be retried")
    # A persisted intent may already have reached Bitbucket. It can only be read.
    job.state = "sending" if job.intent is not None else "queued"
    job.actor_id, job.membership = actor_id, membership_stamp(session, actor_id, product_id)
    job.owner, job.error_code = None, None
    job.updated_at = datetime.now(UTC)
    record_audit(session, actor_id=actor_id, action="branch.retry_requested", entity_id=job.id)


def new_authoring_activity(request_id: UUID, version: int) -> UUID:
    from uuid import NAMESPACE_URL, uuid5

    return uuid5(NAMESPACE_URL, f"verboflex:authoring:{request_id}:{version}")
