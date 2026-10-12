"""Role-gated maximum-length constraint mutation routes."""

import logging
from collections.abc import Callable
from typing import Annotated, Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.auth.translation_access import (
    TranslationGroupAccessMode,
    TranslationGroupAccessUnavailable,
    TranslationGroupActionDenied,
    resolve_translation_group_access,
)
from verboflex.db.session import get_db_session
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.translation_constraints import (
    DeleteTranslationConstraintRequest,
    PutTranslationConstraintRequest,
    TranslationConstraintErrorResponse,
    TranslationConstraintMutationResponse,
    TranslationConstraintMutationValueResponse,
)
from verboflex.schemas.translations import (
    LanguageCode,
    TranslationConstraintProjectionResponse,
)
from verboflex.services.translation_constraints import (
    ConstraintAuthorityUnavailable,
    ConstraintInputInvalid,
    ConstraintMutationProjection,
    ConstraintNotFound,
    ConstraintSource,
    ConstraintVersionConflict,
)
from verboflex.services.translation_constraints import (
    delete_translation_constraint as delete_translation_constraint_service,
)
from verboflex.services.translation_constraints import (
    put_translation_constraint as put_translation_constraint_service,
)
from verboflex.services.translation_search import (
    TranslationGroupUnavailable,
    get_translation_group,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/translations", tags=["translation-constraints"])
ConstraintPrincipal = CurrentPrincipal
ConstraintSession = Annotated[Session, Depends(get_db_session, use_cache=False)]

AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
}
MUTATION_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_404_NOT_FOUND: {"model": TranslationConstraintErrorResponse},
    status.HTTP_409_CONFLICT: {"model": TranslationConstraintErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "content": {
            "application/json": {
                "schema": {
                    "anyOf": [
                        {"$ref": "#/components/schemas/TranslationConstraintErrorResponse"},
                        {"$ref": "#/components/schemas/HTTPValidationError"},
                    ]
                }
            }
        }
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": TranslationConstraintErrorResponse},
}


def _raise_constraint_error(error: Exception) -> NoReturn:
    if isinstance(error, TranslationGroupActionDenied):
        raise HTTPException(403, "Insufficient permissions") from error
    if isinstance(
        error,
        (
            ConstraintAuthorityUnavailable,
            ConstraintNotFound,
            TranslationGroupUnavailable,
            TranslationGroupAccessUnavailable,
        ),
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation unavailable",
        ) from error
    if isinstance(error, ConstraintVersionConflict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Translation constraint conflict",
        ) from error
    if isinstance(error, ConstraintInputInvalid):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid translation constraint input",
        ) from error
    logger.exception("translation constraint mutation failed", exc_info=error)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Translation constraint unavailable",
    ) from error


def _constraint_projection(
    *,
    actual: int,
    maximum: int | None,
    source: ConstraintSource,
    is_over_limit: bool,
) -> TranslationConstraintProjectionResponse:
    if maximum is None:
        return TranslationConstraintProjectionResponse(
            actual=actual,
            maximum=None,
            source=source,
            status="no_max",
            overage=None,
        )
    return TranslationConstraintProjectionResponse(
        actual=actual,
        maximum=maximum,
        source=source,
        status="over_limit" if is_over_limit else "within_limit",
        overage=actual - maximum if is_over_limit else 0,
    )


def _mutation_response(
    projection: ConstraintMutationProjection,
) -> TranslationConstraintMutationResponse:
    values = [
        TranslationConstraintMutationValueResponse(
            id=value.value_id,
            language=value.language,
            constraint=_constraint_projection(
                actual=value.actual,
                maximum=value.maximum,
                source=value.source,
                is_over_limit=value.is_over_limit,
            ),
            approval_eligible=value.approval_eligible,
            submission_eligible=value.submission_eligible,
        )
        for value in projection.values
    ]
    return TranslationConstraintMutationResponse(
        translation_group_id=projection.translation_group_id,
        language=projection.language,
        base_language=projection.base_language,
        explicit_maximum=projection.explicit_maximum,
        version=projection.version,
        violating_count=sum(value.constraint.status == "over_limit" for value in values),
        total_count=len(values),
        values=values,
    )


def _require_active_group(session: Session, *, translation_group_id: UUID) -> None:
    """Apply the same active-product and dataset boundary used by grouped detail."""
    get_translation_group(session, group_id=translation_group_id)


def _execute_mutation(
    session: Session,
    *,
    translation_group_id: UUID,
    principal: CurrentPrincipal,
    operation: Callable[[], ConstraintMutationProjection],
) -> TranslationConstraintMutationResponse:
    """Share currentness, rollback, commit, and bounded error handling."""
    try:
        resolve_translation_group_access(
            session,
            principal=principal,
            translation_group_id=translation_group_id,
            mode=TranslationGroupAccessMode.REVIEW,
        )
        response = _mutation_response(operation())
        session.commit()
    except Exception as error:
        session.rollback()
        _raise_constraint_error(error)
    return response


@router.put(
    "/{translation_group_id}/constraints/{language}",
    operation_id="putTranslationConstraint",
    response_model=TranslationConstraintMutationResponse,
    responses=MUTATION_RESPONSES,
)
def put_translation_constraint(
    translation_group_id: UUID,
    language: LanguageCode,
    payload: PutTranslationConstraintRequest,
    principal: ConstraintPrincipal,
    session: ConstraintSession,
) -> TranslationConstraintMutationResponse:
    """Create or replace one exact maximum under current server authority."""
    return _execute_mutation(
        session,
        translation_group_id=translation_group_id,
        principal=principal,
        operation=lambda: put_translation_constraint_service(
            session,
            translation_group_id=translation_group_id,
            language=language,
            max_chars=payload.max_chars,
            expected_version=payload.expected_version,
            actor_id=principal.user_id,
        ),
    )


@router.delete(
    "/{translation_group_id}/constraints/{language}",
    operation_id="deleteTranslationConstraint",
    response_model=TranslationConstraintMutationResponse,
    responses=MUTATION_RESPONSES,
)
def delete_translation_constraint(
    translation_group_id: UUID,
    language: LanguageCode,
    payload: DeleteTranslationConstraintRequest,
    _principal: ConstraintPrincipal,
    session: ConstraintSession,
) -> TranslationConstraintMutationResponse:
    """Remove one explicit maximum and return its authoritative fallback."""
    return _execute_mutation(
        session,
        translation_group_id=translation_group_id,
        principal=_principal,
        operation=lambda: delete_translation_constraint_service(
            session,
            translation_group_id=translation_group_id,
            language=language,
            expected_version=payload.expected_version,
            actor_id=_principal.user_id,
        ),
    )
