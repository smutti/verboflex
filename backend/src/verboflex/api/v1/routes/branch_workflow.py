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
from verboflex.models.branch_workflow import BranchJob
from verboflex.models.repository import Repository
from verboflex.schemas.branch_workflow import (
    BranchChange,
    BranchWorkflowResponse,
    ConfigureBranchWorkflow,
)
from verboflex.services.branch_workflow import (
    BranchWorkflowError,
    configure,
    has_unpublished_commits,
    request_pr,
    retry_job,
    workflow_for,
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
) -> BranchWorkflowResponse:
    try:
        _product_actor(session, product_id, principal.user_id, action=False)
        workflow = workflow_for(session, product_id)
        if workflow is None:
            return BranchWorkflowResponse(enabled=False)
        repository = session.get_one(Repository, workflow.repository_id)
        can_publish = bool(
            {"admin", "product_manager_reviewer"}.intersection(
                product_roles(session, principal.user_id, product_id)
            )
        )
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
            repository=repository.repository_slug,
            work_branch=workflow.work_branch,
            target_branch=workflow.target_branch,
            can_publish=can_publish,
            can_create_pr=can_publish
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
        configure(
            session, product_id=product_id, actor_id=principal.user_id, **payload.model_dump()
        )
        session.commit()
        return get_workflow(product_id, principal, session)
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
def create_pr(product_id: UUID, principal: CurrentPrincipal, session: DB) -> BranchWorkflowResponse:
    try:
        request_pr(session, product_id=product_id, actor_id=principal.user_id)
        session.commit()
        return get_workflow(product_id, principal, session)
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
        return get_workflow(product_id, principal, session)
    except Exception as error:
        session.rollback()
        _error(error)
        raise
