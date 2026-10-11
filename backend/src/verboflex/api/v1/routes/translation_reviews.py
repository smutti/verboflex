"""Authenticated scalar translation proposal routes."""

import logging
from typing import Annotated, Any, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.auth.translation_access import (
    TranslationGroupAccessUnavailable,
    TranslationGroupActionDenied,
)
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.schemas.reviews import (
    PendingTranslationValueResponse,
    PublishedTranslationValueResponse,
    ReviewActivityCursor,
    ReviewActivityPageResponse,
    ReviewActivityResponse,
    ReviewActivityValueResponse,
    ReviewTransitionConflictResponse,
    ReviewTransitionRequest,
    SaveTranslationProposalRequest,
    SaveTranslationProposalValueRequest,
    TranslationProposalActivityResponse,
    TranslationProposalConflictResponse,
    TranslationProposalErrorResponse,
    TranslationProposalResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.services.translation_reviews import (
    InvalidReviewActivityCursor,
    ProposalBasisStale,
    ProposalReviewBlocked,
    ProposalVersionConflict,
    ReviewActivityPage,
    TranslationProposalActivity,
    TranslationProposalComparison,
    TranslationProposalInputInvalid,
    TranslationProposalProjection,
    TranslationProposalUnavailable,
    list_review_activity,
    save_translation_proposal,
    transition_translation_proposal,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/translations", tags=["translation-reviews"])
TranslationReviewSession = Annotated[Session, Depends(get_db_session, use_cache=False)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]

RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": TranslationProposalErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": TranslationProposalErrorResponse},
    status.HTTP_409_CONFLICT: {"model": TranslationProposalConflictResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "content": {
            "application/json": {
                "schema": {
                    "anyOf": [
                        {"$ref": "#/components/schemas/TranslationProposalErrorResponse"},
                        {"$ref": "#/components/schemas/HTTPValidationError"},
                    ]
                }
            }
        }
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": TranslationProposalErrorResponse},
}

TRANSITION_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": TranslationProposalErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": TranslationProposalErrorResponse},
    status.HTTP_409_CONFLICT: {
        "model": ReviewTransitionConflictResponse | TranslationProposalErrorResponse
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "content": {
            "application/json": {
                "schema": {
                    "anyOf": [
                        {"$ref": "#/components/schemas/TranslationProposalErrorResponse"},
                        {"$ref": "#/components/schemas/HTTPValidationError"},
                    ]
                }
            }
        }
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": TranslationProposalErrorResponse},
}
ACTIVITY_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": TranslationProposalErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": TranslationProposalErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "content": {
            "application/json": {
                "schema": {
                    "anyOf": [
                        {"$ref": "#/components/schemas/TranslationProposalErrorResponse"},
                        {"$ref": "#/components/schemas/HTTPValidationError"},
                    ]
                }
            }
        }
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": TranslationProposalErrorResponse},
}


def _raise_proposal_error(error: Exception) -> NoReturn:
    if isinstance(error, TranslationGroupActionDenied):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Translation action denied",
        ) from error
    if isinstance(error, (TranslationGroupAccessUnavailable, TranslationProposalUnavailable)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation unavailable",
        ) from error
    if isinstance(error, TranslationProposalInputInvalid):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid translation proposal input",
        ) from error
    if isinstance(error, InvalidReviewActivityCursor):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid review activity cursor",
        ) from error
    logger.exception("translation proposal save failed", exc_info=error)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Translation proposal unavailable",
    ) from error


def _activity_values(
    raw: tuple[object, ...] | None,
) -> list[ReviewActivityValueResponse] | None:
    if raw is None:
        return None
    return [ReviewActivityValueResponse.model_validate(item) for item in raw]


def _response(projection: TranslationProposalProjection) -> TranslationProposalResponse:
    activity = projection.activity
    return TranslationProposalResponse(
        translation_group_id=projection.translation_group_id,
        language=projection.language,
        version=projection.version,
        state=projection.state,
        reconciliation_required=projection.reconciliation_required,
        published=[
            PublishedTranslationValueResponse(
                translation_value_id=item.translation_value_id,
                selector_version=1,
                selector_digest=item.selector_digest,
                revision_number=item.revision_number,
                revision_digest=item.revision_digest,
                text=item.text,
                review_state=item.review_state,
            )
            for item in projection.published
        ],
        pending=[
            PendingTranslationValueResponse(
                translation_value_id=item.translation_value_id,
                selector_version=1,
                selector_digest=item.selector_digest,
                basis_revision_number=item.basis_revision_number,
                basis_digest=item.basis_digest,
                text=item.text,
                grapheme_count=item.grapheme_count,
                maximum=item.maximum,
                is_over_limit=item.is_over_limit,
                approval_eligible=item.approval_eligible,
                submission_eligible=item.submission_eligible,
            )
            for item in projection.pending
        ],
        updated_by=projection.updated_by,
        updated_at=projection.updated_at,
        activity=(
            TranslationProposalActivityResponse(
                id=activity.id,
                translation_group_id=activity.translation_group_id,
                language=activity.language,
                kind=activity.kind,
                proposal_version=activity.proposal_version,
                from_state=activity.from_state,
                to_state=activity.to_state,
                before_values=_activity_values(activity.before_values),
                after_values=_activity_values(activity.after_values),
                reason=activity.reason,
                comment_id=activity.comment_id,
                actor_id=activity.actor_id,
                created_at=activity.created_at,
            )
            if activity is not None
            else None
        ),
    )


def _activity_response(activity: TranslationProposalActivity) -> ReviewActivityResponse:
    return ReviewActivityResponse(
        id=activity.id,
        translation_group_id=activity.translation_group_id,
        language=activity.language,
        kind=activity.kind,
        proposal_version=activity.proposal_version,
        from_state=activity.from_state,
        to_state=activity.to_state,
        before_values=_activity_values(activity.before_values),
        after_values=_activity_values(activity.after_values),
        reason=activity.reason,
        comment_id=activity.comment_id,
        actor_id=activity.actor_id,
        created_at=activity.created_at,
    )


def _activity_page_response(page: ReviewActivityPage) -> ReviewActivityPageResponse:
    return ReviewActivityPageResponse(
        items=[_activity_response(activity) for activity in page.items],
        next_cursor=page.next_cursor,
    )


def _conflict_response(
    comparison: TranslationProposalComparison,
    *,
    detail: Literal[
        "Translation proposal conflict",
        "Translation proposal basis stale",
    ],
) -> TranslationProposalConflictResponse:
    return TranslationProposalConflictResponse(
        detail=detail,
        attempted_version=comparison.attempted_version,
        attempted_values=[
            SaveTranslationProposalValueRequest(
                translation_value_id=item.translation_value_id,
                selector_version=1,
                selector_digest=item.selector_digest,
                basis_revision_number=item.basis_revision_number,
                basis_digest=item.basis_digest,
                proposed_text=item.proposed_text,
            )
            for item in comparison.attempted_values
        ],
        latest=_response(comparison.latest) if comparison.latest is not None else None,
    )


@router.put(
    "/{translation_group_id}/proposal",
    operation_id="saveTranslationProposal",
    response_model=TranslationProposalResponse,
    responses=RESPONSES,
)
def put_translation_proposal(
    translation_group_id: UUID,
    payload: SaveTranslationProposalRequest,
    principal: CurrentPrincipal,
    session: TranslationReviewSession,
) -> TranslationProposalResponse | JSONResponse:
    """Persist one complete Draft proposal under caller-owned transaction authority."""
    try:
        projection = save_translation_proposal(
            session,
            principal=principal,
            translation_group_id=translation_group_id,
            values=payload.values,
            expected_version=payload.expected_version,
        )
        response = _response(projection)
        session.commit()
        return response
    except ProposalBasisStale as error:
        session.commit()
        conflict_response = _conflict_response(
            error.comparison,
            detail="Translation proposal basis stale",
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=conflict_response.model_dump(mode="json"),
        )
    except ProposalVersionConflict as error:
        session.rollback()
        conflict_response = _conflict_response(
            error.comparison,
            detail="Translation proposal conflict",
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=conflict_response.model_dump(mode="json"),
        )
    except Exception as error:
        session.rollback()
        _raise_proposal_error(error)


@router.get(
    "/{translation_group_id}/activity",
    operation_id="listTranslationReviewActivity",
    response_model=ReviewActivityPageResponse,
    responses=ACTIVITY_RESPONSES,
)
def get_translation_review_activity(
    translation_group_id: UUID,
    principal: CurrentPrincipal,
    session: TranslationReviewSession,
    settings: SettingsDependency,
    cursor: Annotated[ReviewActivityCursor | None, Query()] = None,
) -> ReviewActivityPageResponse:
    """List complete immutable proposal evidence without provider details."""
    secret = settings.jwt_secret_key
    if secret is None:
        _raise_proposal_error(RuntimeError("review activity cursor signing unavailable"))
    try:
        return _activity_page_response(
            list_review_activity(
                session,
                principal=principal,
                translation_group_id=translation_group_id,
                cursor=cursor,
                cursor_secret=secret.get_secret_value(),
            )
        )
    except Exception as error:
        _raise_proposal_error(error)


@router.post(
    "/{translation_group_id}/proposal/state",
    operation_id="transitionTranslationProposal",
    response_model=TranslationProposalResponse,
    responses=TRANSITION_RESPONSES,
)
def post_translation_proposal_state(
    translation_group_id: UUID,
    payload: ReviewTransitionRequest,
    principal: CurrentPrincipal,
    session: TranslationReviewSession,
) -> TranslationProposalResponse | JSONResponse:
    """Apply one review-only transition without changing imported authority."""
    try:
        projection = transition_translation_proposal(
            session,
            principal=principal,
            translation_group_id=translation_group_id,
            target_state=payload.target_state,
            expected_version=payload.expected_version,
            reason=payload.reason,
        )
        response = _response(projection)
        session.commit()
        return response
    except ProposalVersionConflict as error:
        session.rollback()
        latest = error.comparison.latest
        if latest is None:
            _raise_proposal_error(TranslationProposalUnavailable("translation unavailable"))
        conflict = ReviewTransitionConflictResponse(
            detail="Translation proposal conflict",
            expected_version=error.comparison.attempted_version,
            latest=_response(latest),
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=conflict.model_dump(mode="json"),
        )
    except ProposalReviewBlocked as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Translation proposal review blocked",
        ) from error
    except Exception as error:
        session.rollback()
        _raise_proposal_error(error)
