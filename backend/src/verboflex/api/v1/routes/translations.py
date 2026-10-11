"""Ordinary authenticated translation search and grouped-detail routes."""

import logging
from typing import Annotated, Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.auth.translation_access import (
    TranslationGroupAccessMode,
    TranslationGroupAccessUnavailable,
    TranslationGroupActionDenied,
    resolve_translation_group_access,
)
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.translation_workspace import (
    TranslationKeyPageResponse,
    TranslationKeySearchQuery,
)
from verboflex.schemas.translations import (
    PendingTranslationDetailResponse,
    PendingTranslationSummaryResponse,
    PendingTranslationValueResponse,
    TranslationConstraintProjectionResponse,
    TranslationErrorResponse,
    TranslationGroupDetailResponse,
    TranslationGroupSummaryResponse,
    TranslationHistoryResponse,
    TranslationLanguageOptionResponse,
    TranslationOptionsResponse,
    TranslationProductOptionResponse,
    TranslationProvenanceResponse,
    TranslationSearchPageResponse,
    TranslationSearchQuery,
    TranslationSelectorFieldResponse,
    TranslationSourceComparisonResponse,
    TranslationSourceContextResponse,
    TranslationSummaryProvenanceResponse,
    TranslationValueResponse,
)
from verboflex.services.translation_search import (
    InvalidTranslationCursor,
    TranslationGroupDetail,
    TranslationSearchFilters,
    TranslationSearchInputError,
    TranslationValueDetail,
    get_translation_options,
    language_label,
    search_translations,
)
from verboflex.services.translation_workspace import search_translation_keys

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/translations", tags=["translations"])
TranslationSession = Annotated[Session, Depends(get_db_session, use_cache=False)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]

AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
}
SEARCH_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "content": {
            "application/json": {
                "schema": {
                    "anyOf": [
                        {"$ref": "#/components/schemas/TranslationErrorResponse"},
                        {"$ref": "#/components/schemas/HTTPValidationError"},
                    ]
                }
            }
        }
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": TranslationErrorResponse},
}
DETAIL_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_404_NOT_FOUND: {"model": TranslationErrorResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": TranslationErrorResponse},
}


def _service_unavailable(error: Exception) -> NoReturn:
    logger.exception("translation read failed", exc_info=error)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Translation search unavailable",
    ) from error


def _constraint_response(
    value: TranslationValueDetail,
) -> TranslationConstraintProjectionResponse:
    constraint = value.constraint
    return TranslationConstraintProjectionResponse(
        actual=constraint.actual,
        maximum=constraint.maximum,
        source=constraint.source,
        status=constraint.status,
        overage=constraint.overage,
    )


def _value_response(value: TranslationValueDetail) -> TranslationValueResponse:
    provenance = value.provenance
    return TranslationValueResponse(
        id=value.id,
        selector_version=value.selector_version,
        selector_kind=value.selector_kind,
        selector_digest=value.selector_digest,
        selector_fields=(
            [
                TranslationSelectorFieldResponse.model_validate(field)
                for field in value.selector_fields
            ]
            if value.selector_fields is not None
            else None
        ),
        history=[TranslationHistoryResponse.model_validate(entry) for entry in value.history],
        history_has_more=value.history_has_more,
        source_text=value.source_text,
        source_value_id=value.source_value_id,
        source_resolution=value.source_resolution,
        source_comparison=(
            TranslationSourceComparisonResponse.model_validate(value.source_comparison)
            if value.source_comparison is not None
            else None
        ),
        translated_text=value.translated_text,
        display_text=value.display_text,
        structure=list(value.structure),
        review_state=value.review_state,
        grapheme_count=value.grapheme_count,
        constraint=_constraint_response(value),
        is_deleted=value.is_deleted,
        deleted_at=value.deleted_at,
        provenance=(
            TranslationProvenanceResponse(
                repository_id=provenance.repository_id,
                repository_name=provenance.repository_name,
                repository_side=provenance.repository_side,
                branch=provenance.branch,
                path=provenance.path,
                format=provenance.format,
                commit_hash=provenance.commit_hash,
                execution_id=provenance.execution_id,
                line=provenance.line,
                column=provenance.column,
            )
            if provenance is not None
            else None
        ),
    )


def _detail_response(detail: TranslationGroupDetail) -> TranslationGroupDetailResponse:
    pending = detail.pending_change
    return TranslationGroupDetailResponse(
        id=detail.id,
        product_id=detail.product_id,
        product_name=detail.product_name,
        raw_key=detail.raw_key,
        language=detail.language,
        language_label=language_label(detail.language),
        base_language=detail.base_language,
        explicit_maximum=detail.explicit_maximum,
        constraint_version=detail.constraint_version,
        base_maximum=detail.base_maximum,
        states=list(detail.states),
        state_summary=detail.state_summary,
        is_deleted=detail.is_deleted,
        values=[_value_response(value) for value in detail.values],
        pending_change=(
            PendingTranslationDetailResponse(
                version=pending.version,
                state=pending.state,
                reconciliation_required=pending.reconciliation_required,
                updated_by=pending.updated_by,
                updated_at=pending.updated_at,
                values=[
                    PendingTranslationValueResponse(
                        translation_value_id=value.translation_value_id,
                        selector_version=value.selector_version,
                        selector_digest=value.selector_digest,
                        basis_revision_number=value.basis_revision_number,
                        basis_digest=value.basis_digest,
                        text=value.text,
                        grapheme_count=value.grapheme_count,
                        maximum=value.maximum,
                        is_over_limit=value.is_over_limit,
                        approval_eligible=value.approval_eligible,
                        submission_eligible=value.submission_eligible,
                    )
                    for value in pending.values
                ],
            )
            if pending is not None
            else None
        ),
        comment_count=detail.comment_count,
        mutation_eligible=detail.mutation_eligible,
        review_eligible=detail.review_eligible,
        source_context=[
            TranslationSourceContextResponse.model_validate(source)
            for source in detail.source_context
        ]
        if detail.source_context is not None
        else None,
    )


@router.get(
    "/options",
    operation_id="listTranslationOptions",
    response_model=TranslationOptionsResponse,
    responses={
        **AUTH_RESPONSES,
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": TranslationErrorResponse},
    },
)
def list_translation_options(
    _principal: CurrentPrincipal,
    session: TranslationSession,
    product_id: Annotated[UUID | None, Query()] = None,
) -> TranslationOptionsResponse:
    """List exact active products and languages available to the principal."""
    try:
        options = get_translation_options(session, product_id=product_id)
    except Exception as error:
        _service_unavailable(error)
    return TranslationOptionsResponse(
        products=[
            TranslationProductOptionResponse(id=product.id, name=product.name)
            for product in options.products
        ],
        languages=[
            TranslationLanguageOptionResponse(code=language.code, label=language.label)
            for language in options.languages
        ],
    )


@router.get(
    "",
    operation_id="searchTranslations",
    response_model=TranslationSearchPageResponse,
    responses=SEARCH_RESPONSES,
)
def search_translation_collection(
    principal: CurrentPrincipal,
    session: TranslationSession,
    settings: SettingsDependency,
    query: Annotated[TranslationSearchQuery, Query()],
) -> TranslationSearchPageResponse:
    """Search current canonical groups through one fixed keyset envelope."""
    secret = settings.jwt_secret_key
    if secret is None:
        _service_unavailable(RuntimeError("cursor signing is unavailable"))
    try:
        page = search_translations(
            session,
            principal_id=principal.user_id,
            filters=TranslationSearchFilters(
                query=query.q,
                product_id=query.product_id,
                language=query.language,
                state=query.state,
                violation=query.violation,
                work_status=query.work_status,
                deleted=query.deleted,
                page_size=query.page_size,
            ),
            cursor=query.cursor,
            cursor_secret=secret.get_secret_value(),
        )
    except InvalidTranslationCursor as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid translation cursor",
        ) from error
    except TranslationSearchInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid translation cursor",
        ) from error
    except Exception as error:
        _service_unavailable(error)
    return TranslationSearchPageResponse(
        items=[
            TranslationGroupSummaryResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product_name,
                raw_key=item.raw_key,
                language=item.language,
                language_label=language_label(item.language),
                rank=item.rank,
                source_text=item.source_text,
                source_language=item.source_language,
                translated_text=item.translated_text,
                selector_kinds=list(item.selector_kinds),
                provenance=(
                    TranslationSummaryProvenanceResponse(
                        repository_name=item.provenance.repository_name,
                        branch=item.provenance.branch,
                        path=item.provenance.path,
                    )
                    if item.provenance is not None
                    else None
                ),
                value_count=item.value_count,
                over_limit_count=item.over_limit_count,
                within_limit_count=item.within_limit_count,
                no_max_count=item.no_max_count,
                states=list(item.states),
                state_summary=item.state_summary,
                has_over_limit=item.has_over_limit,
                has_no_max=item.has_no_max,
                is_deleted=item.is_deleted,
                pending_change=(
                    PendingTranslationSummaryResponse(
                        version=item.pending_change.version,
                        state=item.pending_change.state,
                        reconciliation_required=item.pending_change.reconciliation_required,
                        value_count=item.pending_change.value_count,
                    )
                    if item.pending_change is not None
                    else None
                ),
                comment_count=item.comment_count,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/keys",
    operation_id="searchTranslationKeys",
    response_model=TranslationKeyPageResponse,
    responses=SEARCH_RESPONSES,
)
def search_translation_key_collection(
    principal: CurrentPrincipal,
    session: TranslationSession,
    settings: SettingsDependency,
    query: Annotated[TranslationKeySearchQuery, Query()],
) -> TranslationKeyPageResponse:
    """Page exact canonical keys, then project all selected language aggregates."""
    secret = settings.jwt_secret_key
    if secret is None:
        _service_unavailable(RuntimeError("cursor signing is unavailable"))
    try:
        return search_translation_keys(
            session,
            principal_id=principal.user_id,
            query=query,
            cursor_secret=secret.get_secret_value(),
        )
    except (InvalidTranslationCursor, TranslationSearchInputError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid translation cursor",
        ) from error
    except Exception as error:
        _service_unavailable(error)


@router.get(
    "/{translation_group_id}",
    operation_id="getTranslationGroup",
    response_model=TranslationGroupDetailResponse,
    responses=DETAIL_RESPONSES,
)
def get_translation_group_detail(
    translation_group_id: UUID,
    principal: CurrentPrincipal,
    session: TranslationSession,
) -> TranslationGroupDetailResponse:
    """Return one complete group or the same bounded unavailable response."""
    try:
        access = resolve_translation_group_access(
            session,
            principal=principal,
            translation_group_id=translation_group_id,
            mode=TranslationGroupAccessMode.READ,
        )
    except TranslationGroupAccessUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation unavailable",
        ) from error
    except TranslationGroupActionDenied as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Translation action denied",
        ) from error
    except Exception as error:
        _service_unavailable(error)
    return _detail_response(access.group)
