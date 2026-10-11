"""Database-only product review HTTP operations."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.localization.writing.core import WritebackRejected
from verboflex.schemas.submissions import (
    ChangeSetActivityPage,
    ChangeSetCandidatesResponse,
    ChangeSetFilesPage,
    ChangeSetHistoryPage,
    ChangeSetItemsPage,
    ChangeSetResponse,
    ChangeSetValuesPage,
    CreateSubmissionBatchRequest,
    CreateSubmissionReviewRequest,
    ReviewFilesPage,
    ReviewValuesPage,
    SubmissionActionRequest,
    SubmissionBatchResponse,
    SubmissionReviewError,
    SubmissionReviewResponse,
)
from verboflex.services.submission_history import (
    InvalidSubmissionCursor,
    list_change_set_activity,
    list_change_set_files,
    list_change_set_items,
    list_change_set_values,
    list_change_sets,
)
from verboflex.services.submission_recovery import (
    enqueue_reconciliation,
    finalize_known_pre_pr,
    request_reconcile,
    request_retry,
)
from verboflex.services.submission_reviews import (
    SubmissionReviewDenied,
    SubmissionReviewUnavailable,
    create_submission_review,
    enqueue_submission_review,
    get_review_files,
    get_review_values,
    get_submission_review,
    list_change_set_candidates,
)
from verboflex.services.submissions import (
    SubmissionConflict,
    create_submission_batch,
    enqueue_submission,
    get_change_set,
    get_submission_batch,
    get_submission_batch_by_key,
)

router = APIRouter(prefix="/products/{product_id}", tags=["submissions"])
ReviewSession = Annotated[Session, Depends(get_db_session, use_cache=False)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
HistoryCursor = Annotated[str | None, Query(min_length=1, max_length=2048)]
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": SubmissionReviewError} for code in (403, 404, 409)
}


def _error(error: Exception) -> JSONResponse:
    if isinstance(error, InvalidSubmissionCursor):
        code, reason, message = 422, "invalid_cursor", "Invalid submission cursor"
    elif isinstance(error, SubmissionReviewUnavailable):
        code, reason, message = 404, "unavailable", "Review unavailable"
    elif isinstance(error, SubmissionReviewDenied):
        code, reason, message = 403, "denied", "Review action denied"
    elif isinstance(error, WritebackRejected):
        code, reason, message = 409, error.reason.value, str(error)
    elif isinstance(error, SubmissionConflict):
        code, reason, message = 409, error.code, str(error)
    else:
        raise error
    return JSONResponse(status_code=code, content={"detail": message, "code": reason})


@router.get(
    "/change-set-candidates",
    response_model=ChangeSetCandidatesResponse,
    responses=ERRORS,
    operation_id="getChangeSetCandidates",
)
def candidates(
    product_id: UUID,
    principal: CurrentPrincipal,
    session: ReviewSession,
    after: UUID | None = None,
    state: Literal["approved", "draft", "rejected", "all"] = "approved",
    query: Annotated[str, Query(max_length=256)] = "",
    language: Annotated[str, Query(max_length=64)] = "",
    translation_group_id: UUID | None = None,
) -> ChangeSetCandidatesResponse | JSONResponse:
    try:
        return list_change_set_candidates(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            after=after,
            state=state,
            query=query,
            language=language,
            translation_group_id=translation_group_id,
        )
    except (SubmissionReviewUnavailable, SubmissionReviewDenied, WritebackRejected) as error:
        return _error(error)


@router.post(
    "/submission-reviews",
    status_code=202,
    response_model=SubmissionReviewResponse,
    responses=ERRORS,
    operation_id="createSubmissionReview",
)
def create(
    product_id: UUID,
    body: CreateSubmissionReviewRequest,
    request: Request,
    principal: CurrentPrincipal,
    session: ReviewSession,
) -> SubmissionReviewResponse | JSONResponse:
    try:
        return create_submission_review(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            proposals=body.proposals,
            targets=tuple(body.targets),
            enqueuer=getattr(
                request.app.state, "submission_review_enqueuer", enqueue_submission_review
            ),
        )
    except (SubmissionReviewUnavailable, SubmissionReviewDenied, WritebackRejected) as error:
        return _error(error)


@router.get(
    "/submission-reviews/{review_id}/files",
    response_model=ReviewFilesPage,
    responses=ERRORS,
    operation_id="getSubmissionReviewFiles",
)
def files(
    product_id: UUID,
    review_id: UUID,
    principal: CurrentPrincipal,
    session: ReviewSession,
    after: Annotated[int, Query(ge=0, le=500)] = 0,
) -> ReviewFilesPage | JSONResponse:
    try:
        return get_review_files(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            review_id=review_id,
            after=after,
        )
    except (SubmissionReviewUnavailable, SubmissionReviewDenied, WritebackRejected) as error:
        return _error(error)


@router.get(
    "/submission-reviews/{review_id}/values",
    response_model=ReviewValuesPage,
    responses=ERRORS,
    operation_id="getSubmissionReviewValues",
)
def values(
    product_id: UUID,
    review_id: UUID,
    principal: CurrentPrincipal,
    session: ReviewSession,
    after: Annotated[int, Query(ge=0, le=5000)] = 0,
) -> ReviewValuesPage | JSONResponse:
    try:
        return get_review_values(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            review_id=review_id,
            after=after,
        )
    except (SubmissionReviewUnavailable, SubmissionReviewDenied, WritebackRejected) as error:
        return _error(error)


@router.get(
    "/submission-reviews/{review_id}",
    response_model=SubmissionReviewResponse,
    responses=ERRORS,
    operation_id="getSubmissionReview",
)
def get(
    product_id: UUID, review_id: UUID, principal: CurrentPrincipal, session: ReviewSession
) -> SubmissionReviewResponse | JSONResponse:
    try:
        return get_submission_review(
            session, product_id=product_id, actor_id=principal.user_id, review_id=review_id
        )
    except (SubmissionReviewUnavailable, SubmissionReviewDenied, WritebackRejected) as error:
        return _error(error)


SUBMISSION_ERRORS = (
    SubmissionReviewUnavailable,
    SubmissionReviewDenied,
    WritebackRejected,
    SubmissionConflict,
)


@router.post(
    "/submission-batches",
    status_code=202,
    response_model=SubmissionBatchResponse,
    responses=ERRORS,
    operation_id="createSubmissionBatch",
)
def submit(
    product_id: UUID,
    body: CreateSubmissionBatchRequest,
    request: Request,
    principal: CurrentPrincipal,
    session: ReviewSession,
) -> SubmissionBatchResponse | JSONResponse:
    try:
        return create_submission_batch(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            request=body,
            enqueuer=getattr(request.app.state, "submission_enqueuer", enqueue_submission),
        )
    except SUBMISSION_ERRORS as error:
        return _error(error)


def _cursor_secret(settings: Settings) -> str:
    if settings.jwt_secret_key is None:
        raise HTTPException(status_code=503, detail="History temporarily unavailable")
    return settings.jwt_secret_key.get_secret_value()


@router.get(
    "/change-sets",
    response_model=ChangeSetHistoryPage,
    responses=ERRORS,
    operation_id="listChangeSets",
)
def history(
    product_id: UUID,
    principal: CurrentPrincipal,
    session: ReviewSession,
    settings: SettingsDependency,
    cursor: HistoryCursor = None,
    key_id: UUID | None = None,
) -> ChangeSetHistoryPage | JSONResponse:
    try:
        return list_change_sets(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            cursor=cursor,
            key_id=key_id,
            cursor_secret=_cursor_secret(settings),
        )
    except (*SUBMISSION_ERRORS, InvalidSubmissionCursor) as error:
        return _error(error)


@router.get(
    "/change-sets/{change_set_id}/items",
    response_model=ChangeSetItemsPage,
    responses=ERRORS,
    operation_id="getChangeSetItems",
)
def history_items(
    product_id: UUID,
    change_set_id: UUID,
    principal: CurrentPrincipal,
    session: ReviewSession,
    settings: SettingsDependency,
    cursor: HistoryCursor = None,
) -> ChangeSetItemsPage | JSONResponse:
    try:
        return list_change_set_items(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            change_set_id=change_set_id,
            cursor=cursor,
            cursor_secret=_cursor_secret(settings),
        )
    except (*SUBMISSION_ERRORS, InvalidSubmissionCursor) as error:
        return _error(error)


@router.get(
    "/change-sets/{change_set_id}/values",
    response_model=ChangeSetValuesPage,
    responses=ERRORS,
    operation_id="getChangeSetValues",
)
def history_values(
    product_id: UUID,
    change_set_id: UUID,
    principal: CurrentPrincipal,
    session: ReviewSession,
    settings: SettingsDependency,
    cursor: HistoryCursor = None,
) -> ChangeSetValuesPage | JSONResponse:
    try:
        return list_change_set_values(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            change_set_id=change_set_id,
            cursor=cursor,
            cursor_secret=_cursor_secret(settings),
        )
    except (*SUBMISSION_ERRORS, InvalidSubmissionCursor) as error:
        return _error(error)


@router.get(
    "/change-sets/{change_set_id}/files",
    response_model=ChangeSetFilesPage,
    responses=ERRORS,
    operation_id="getChangeSetFiles",
)
def history_files(
    product_id: UUID,
    change_set_id: UUID,
    principal: CurrentPrincipal,
    session: ReviewSession,
    settings: SettingsDependency,
    cursor: HistoryCursor = None,
) -> ChangeSetFilesPage | JSONResponse:
    try:
        return list_change_set_files(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            change_set_id=change_set_id,
            cursor=cursor,
            cursor_secret=_cursor_secret(settings),
        )
    except (*SUBMISSION_ERRORS, InvalidSubmissionCursor) as error:
        return _error(error)


@router.get(
    "/change-sets/{change_set_id}/activity",
    response_model=ChangeSetActivityPage,
    responses=ERRORS,
    operation_id="getChangeSetActivity",
)
def history_activity(
    product_id: UUID,
    change_set_id: UUID,
    principal: CurrentPrincipal,
    session: ReviewSession,
    settings: SettingsDependency,
    cursor: HistoryCursor = None,
) -> ChangeSetActivityPage | JSONResponse:
    try:
        return list_change_set_activity(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            change_set_id=change_set_id,
            cursor=cursor,
            cursor_secret=_cursor_secret(settings),
        )
    except (*SUBMISSION_ERRORS, InvalidSubmissionCursor) as error:
        return _error(error)


@router.get(
    "/submission-batches/by-key/{request_key}",
    response_model=SubmissionBatchResponse,
    responses=ERRORS,
    operation_id="getSubmissionBatchByKey",
)
def batch_by_key(
    product_id: UUID,
    request_key: UUID,
    principal: CurrentPrincipal,
    session: ReviewSession,
) -> SubmissionBatchResponse | JSONResponse:
    try:
        return get_submission_batch_by_key(
            session, product_id=product_id, actor_id=principal.user_id, request_key=request_key
        )
    except SUBMISSION_ERRORS as error:
        return _error(error)


@router.get(
    "/submission-batches/{batch_id}",
    response_model=SubmissionBatchResponse,
    responses=ERRORS,
    operation_id="getSubmissionBatch",
)
def batch_detail(
    product_id: UUID,
    batch_id: UUID,
    principal: CurrentPrincipal,
    session: ReviewSession,
) -> SubmissionBatchResponse | JSONResponse:
    try:
        return get_submission_batch(
            session, product_id=product_id, actor_id=principal.user_id, batch_id=batch_id
        )
    except SUBMISSION_ERRORS as error:
        return _error(error)


@router.get(
    "/change-sets/{change_set_id}",
    response_model=ChangeSetResponse,
    responses=ERRORS,
    operation_id="getChangeSet",
)
def group_detail(
    product_id: UUID,
    change_set_id: UUID,
    principal: CurrentPrincipal,
    session: ReviewSession,
) -> ChangeSetResponse | JSONResponse:
    try:
        return get_change_set(
            session, product_id=product_id, actor_id=principal.user_id, change_set_id=change_set_id
        )
    except SUBMISSION_ERRORS as error:
        return _error(error)


@router.post(
    "/change-sets/{change_set_id}/retry",
    status_code=202,
    response_model=ChangeSetResponse,
    responses=ERRORS,
    operation_id="retryChangeSet",
)
def retry_group(
    product_id: UUID,
    change_set_id: UUID,
    body: SubmissionActionRequest,
    request: Request,
    principal: CurrentPrincipal,
    session: ReviewSession,
) -> ChangeSetResponse | JSONResponse:
    try:
        return request_retry(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            change_set_id=change_set_id,
            expected_attempt=body.expected_attempt,
            enqueuer=getattr(request.app.state, "submission_enqueuer", enqueue_submission),
        )
    except SUBMISSION_ERRORS as error:
        return _error(error)


@router.post(
    "/change-sets/{change_set_id}/reconcile",
    status_code=202,
    response_model=ChangeSetResponse,
    responses=ERRORS,
    operation_id="reconcileChangeSet",
)
def reconcile_group(
    product_id: UUID,
    change_set_id: UUID,
    body: SubmissionActionRequest,
    request: Request,
    principal: CurrentPrincipal,
    session: ReviewSession,
) -> ChangeSetResponse | JSONResponse:
    try:
        return request_reconcile(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            change_set_id=change_set_id,
            expected_attempt=body.expected_attempt,
            enqueuer=getattr(
                request.app.state, "submission_reconciliation_enqueuer", enqueue_reconciliation
            ),
        )
    except SUBMISSION_ERRORS as error:
        return _error(error)


@router.post(
    "/change-sets/{change_set_id}/finalize",
    response_model=ChangeSetResponse,
    responses=ERRORS,
    operation_id="finalizeChangeSet",
)
def finalize_group(
    product_id: UUID,
    change_set_id: UUID,
    body: SubmissionActionRequest,
    principal: CurrentPrincipal,
    session: ReviewSession,
) -> ChangeSetResponse | JSONResponse:
    try:
        return finalize_known_pre_pr(
            session,
            product_id=product_id,
            actor_id=principal.user_id,
            change_set_id=change_set_id,
            expected_attempt=body.expected_attempt,
        )
    except SUBMISSION_ERRORS as error:
        return _error(error)
