"""Product language initialization; HTTP performs authorization and outbox writes only."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.db.session import get_db_session
from verboflex.localization.writing.core import WritebackRejected
from verboflex.schemas.submissions import ClosedModel
from verboflex.services.branch_workflow import BranchWorkflowError
from verboflex.services.html_languages import discard_language_job
from verboflex.services.project_languages import CreateProjectLanguage, queue_project_language
from verboflex.services.submission_reviews import (
    SubmissionReviewDenied,
    SubmissionReviewUnavailable,
)

router = APIRouter(
    tags=["project-languages"],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Action not permitted"},
        404: {"description": "Product unavailable"},
        409: {"description": "Source or branch conflict"},
    },
)
Db = Annotated[Session, Depends(get_db_session)]


class LanguageJobResponse(ClosedModel):
    id: UUID
    state: str


@router.post(
    "/products/{product_id}/languages",
    response_model=LanguageJobResponse,
    operation_id="createProjectLanguage",
    status_code=202,
)
def create_language(
    product_id: UUID, body: CreateProjectLanguage, principal: CurrentPrincipal, session: Db
) -> LanguageJobResponse:
    try:
        with session.begin():
            job = queue_project_language(
                session, product_id=product_id, actor_id=principal.user_id, body=body
            )
            return LanguageJobResponse(id=job.id, state=job.state)
    except SubmissionReviewUnavailable:
        raise HTTPException(404, "Product unavailable") from None
    except SubmissionReviewDenied:
        raise HTTPException(403, "Action not permitted") from None
    except (BranchWorkflowError, WritebackRejected) as error:
        raise HTTPException(409, str(error)) from None


@router.delete(
    "/products/{product_id}/languages/{job_id}",
    response_model=LanguageJobResponse,
    operation_id="discardProjectLanguage",
)
def discard_language(
    product_id: UUID, job_id: UUID, principal: CurrentPrincipal, session: Db
) -> LanguageJobResponse:
    try:
        with session.begin():
            discard_language_job(
                session, product_id=product_id, actor_id=principal.user_id, job_id=job_id
            )
        return LanguageJobResponse(id=job_id, state="declined")
    except SubmissionReviewUnavailable:
        raise HTTPException(404, "Product unavailable") from None
    except SubmissionReviewDenied:
        raise HTTPException(403, "Action not permitted") from None
    except BranchWorkflowError as error:
        raise HTTPException(409, str(error)) from None
