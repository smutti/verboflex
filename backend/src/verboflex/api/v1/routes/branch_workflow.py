"""Repository work is queued durably; HTTP performs no provider I/O."""

from typing import Annotated, Literal, cast
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.auth.product_access import product_roles
from verboflex.db.session import get_db_session
from verboflex.models.branch_workflow import BranchJob, BranchWorkflow
from verboflex.models.product_mapping import ProductMappingRepositorySide, ProductRepositoryMapping
from verboflex.models.repository import Repository
from verboflex.schemas.branch_workflow import (
    BranchChange,
    BranchMappingChoice,
    BranchWorkflowChoice,
    BranchWorkflowResponse,
    ConfigureBranchWorkflow,
)
from verboflex.services.branch_workflow import (
    BranchWorkflowError,
    active_mapping,
    configure,
    has_unpublished_commits,
    request_pr,
    retry_job,
    workflow_for,
    workflow_for_mapping,
)
from verboflex.services.submission_reviews import (
    SubmissionReviewDenied,
    SubmissionReviewUnavailable,
    _product_actor,
)

router = APIRouter(prefix="/products/{product_id}/branch-workflow", tags=["submissions"])
DB = Annotated[Session, Depends(get_db_session, use_cache=False)]


def _error(error: Exception) -> None:
    if isinstance(error, SubmissionReviewUnavailable):
        raise HTTPException(404, "Product unavailable") from error
    if isinstance(error, SubmissionReviewDenied):
        raise HTTPException(403, "Action not permitted") from error
    if isinstance(error, BranchWorkflowError):
        raise HTTPException(409, str(error)) from error
    if isinstance(error, IntegrityError):
        raise HTTPException(409, "This working branch is already configured") from error
    raise error


@router.get("", operation_id="getBranchWorkflow", response_model=BranchWorkflowResponse)
def get_workflow(
    product_id: UUID,
    principal: CurrentPrincipal,
    session: DB,
    before: Annotated[int | None, Query(ge=1)] = None,
    workflow_id: UUID | None = None,
) -> BranchWorkflowResponse:
    try:
        product, _ = _product_actor(session, product_id, principal.user_id, action=False)
        roles = product_roles(session, principal.user_id, product_id)
        workflows = list(
            session.scalars(
                select(BranchWorkflow)
                .where(BranchWorkflow.product_id == product_id)
                .order_by(BranchWorkflow.created_at, BranchWorkflow.id)
            )
        )
        choices = [
            BranchWorkflowChoice(
                id=w.id,
                repository=session.get_one(Repository, w.repository_id).repository_slug,
                work_branch=w.work_branch,
                target_branch=w.target_branch,
                active=active_mapping(session, w) is not None,
            )
            for w in workflows
        ]
        mappings = []
        if "admin" in roles:
            for m, side, repo in session.execute(
                select(ProductRepositoryMapping, ProductMappingRepositorySide, Repository)
                .select_from(ProductRepositoryMapping)
                .join(ProductMappingRepositorySide)
                .join(Repository)
                .where(
                    ProductRepositoryMapping.revision_id == product.active_revision_id,
                    ProductMappingRepositorySide.role.in_(("direct", "translations")),
                    Repository.provider == "bitbucket",
                )
                .order_by(Repository.repository_slug, ProductRepositoryMapping.id)
            ):
                configured = workflow_for_mapping(session, product_id, m)
                mappings.append(
                    BranchMappingChoice(
                        mapping_id=m.id,
                        repository=repo.repository_slug,
                        source_branch=side.source_branch,
                        workflow_id=configured.id if configured else None,
                    )
                )
        workflow = workflow_for(session, product_id, workflow_id=workflow_id)
        if workflow_id is not None and workflow is None:
            raise SubmissionReviewUnavailable("Workflow unavailable")
        if workflow is None:
            return BranchWorkflowResponse(enabled=False, available_mappings=mappings)
        repository = session.get_one(Repository, workflow.repository_id)
        can_publish = bool({"admin", "product_manager_reviewer"}.intersection(roles))
        query = select(BranchJob).where(BranchJob.workflow_id == workflow.id)
        if before is not None:
            query = query.where(BranchJob.sequence < before)
        rows = list(session.scalars(query.order_by(BranchJob.sequence.desc()).limit(51)))
        pending = session.scalar(
            select(BranchJob.id)
            .where(
                BranchJob.workflow_id == workflow.id,
                BranchJob.state.in_(("queued", "running", "sending", "blocked", "open")),
            )
            .limit(1)
        )
        base = (
            f"https://bitbucket.org/{quote(repository.workspace, safe='')}/"
            f"{quote(repository.repository_slug, safe='')}"
        )
        items = [
            BranchChange(
                id=j.id,
                sequence=j.sequence,
                kind=cast(Literal["commit", "pull_request"], j.kind),
                state=cast(
                    Literal[
                        "queued",
                        "running",
                        "sending",
                        "committed",
                        "open",
                        "merged",
                        "declined",
                        "blocked",
                    ],
                    j.state,
                ),
                label=j.label,
                created_at=j.created_at,
                commit_hash=j.commit_hash,
                commit_url=f"{base}/commits/{j.commit_hash}" if j.commit_hash else None,
                pr_url=j.pr_url,
                error_code=j.error_code,
                can_retry=can_publish and j.state == "blocked",
            )
            for j in rows[:50]
        ]
        return BranchWorkflowResponse(
            enabled=True,
            workflow_id=workflow.id,
            workflows=choices,
            available_mappings=mappings,
            repository=repository.repository_slug,
            work_branch=workflow.work_branch,
            target_branch=workflow.target_branch,
            can_publish=can_publish,
            can_create_pr=can_publish
            and active_mapping(session, workflow) is not None
            and pending is None
            and has_unpublished_commits(session, workflow.id),
            items=items,
            next_before=rows[49].sequence if len(rows) > 50 else None,
        )
    except Exception as error:
        _error(error)
        raise


@router.put("", operation_id="configureBranchWorkflow", response_model=BranchWorkflowResponse)
def put_workflow(
    product_id: UUID, principal: CurrentPrincipal, session: DB, payload: ConfigureBranchWorkflow
) -> BranchWorkflowResponse:
    try:
        configured = configure(
            session, product_id=product_id, actor_id=principal.user_id, **payload.model_dump()
        )
        session.commit()
        return get_workflow(product_id, principal, session, workflow_id=configured.id)
    except Exception as error:
        session.rollback()
        _error(error)
        raise


@router.post(
    "/pull-request",
    operation_id="createBranchPullRequest",
    response_model=BranchWorkflowResponse,
    status_code=202,
)
def create_pr(
    product_id: UUID, principal: CurrentPrincipal, session: DB, workflow_id: UUID | None = None
) -> BranchWorkflowResponse:
    try:
        job = request_pr(
            session, product_id=product_id, actor_id=principal.user_id, workflow_id=workflow_id
        )
        session.commit()
        return get_workflow(product_id, principal, session, workflow_id=job.workflow_id)
    except Exception as error:
        session.rollback()
        _error(error)
        raise


@router.post(
    "/jobs/{job_id}/retry",
    operation_id="retryBranchChange",
    response_model=BranchWorkflowResponse,
    status_code=202,
)
def retry(
    product_id: UUID, job_id: UUID, principal: CurrentPrincipal, session: DB
) -> BranchWorkflowResponse:
    try:
        retry_job(session, product_id=product_id, actor_id=principal.user_id, job_id=job_id)
        session.commit()
        job = session.get_one(BranchJob, job_id)
        return get_workflow(product_id, principal, session, workflow_id=job.workflow_id)
    except Exception as error:
        session.rollback()
        _error(error)
        raise
