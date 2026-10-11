"""Authenticated stable translation discussion routes."""

import logging
from typing import Annotated, Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from verboflex.auth.principal import CurrentPrincipal
from verboflex.auth.translation_access import (
    TranslationGroupAccessUnavailable,
    TranslationGroupActionDenied,
)
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.schemas.comments import (
    CommentAnchorWindowResponse,
    CommentCursor,
    CreateTranslationCommentRequest,
    MentionResponse,
    TranslationCommentAuthorResponse,
    TranslationCommentConflictResponse,
    TranslationCommentErrorResponse,
    TranslationCommentPageResponse,
    TranslationCommentResponse,
    TranslationCommentVersionPageResponse,
    TranslationCommentVersionResponse,
    UpdateTranslationCommentRequest,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.services.notifications import (
    NotificationRedisClient,
    get_notification_redis_client,
    publish_notification_invalidations,
)
from verboflex.services.translation_comments import (
    CommentAnchorWindow,
    CommentVersionConflict,
    InvalidTranslationCommentCursor,
    TranslationCommentActionDenied,
    TranslationCommentInputInvalid,
    TranslationCommentPage,
    TranslationCommentProjection,
    TranslationCommentUnavailable,
    TranslationCommentVersionPage,
    create_translation_comment,
    delete_translation_comment,
    edit_translation_comment,
    get_translation_comment_anchor,
    list_comment_versions,
    list_translation_comments,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/translations", tags=["translation-comments"])
CommentSession = Annotated[Session, Depends(get_db_session, use_cache=False)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
NotificationRedisDependency = Annotated[
    NotificationRedisClient, Depends(get_notification_redis_client)
]

RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": TranslationCommentErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": TranslationCommentErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "content": {
            "application/json": {
                "schema": {
                    "anyOf": [
                        {"$ref": "#/components/schemas/TranslationCommentErrorResponse"},
                        {"$ref": "#/components/schemas/HTTPValidationError"},
                    ]
                }
            }
        }
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": TranslationCommentErrorResponse},
}
MUTATION_RESPONSES = {
    **RESPONSES,
    status.HTTP_409_CONFLICT: {"model": TranslationCommentConflictResponse},
}


def _raise_comment_error(error: Exception) -> NoReturn:
    if isinstance(error, (TranslationGroupActionDenied, TranslationCommentActionDenied)):
        raise HTTPException(status_code=403, detail="Comment action denied") from error
    if isinstance(
        error,
        (
            TranslationGroupAccessUnavailable,
            TranslationCommentUnavailable,
        ),
    ):
        raise HTTPException(status_code=404, detail="Comment unavailable") from error
    if isinstance(error, InvalidTranslationCommentCursor):
        raise HTTPException(status_code=422, detail="Invalid comment cursor") from error
    if isinstance(error, TranslationCommentInputInvalid):
        raise HTTPException(status_code=422, detail="Invalid comment input") from error
    logger.exception("translation comment operation failed", exc_info=error)
    raise HTTPException(status_code=503, detail="Comment unavailable") from error


def _response(item: TranslationCommentProjection) -> TranslationCommentResponse:
    return TranslationCommentResponse(
        id=item.id,
        translation_group_id=item.translation_group_id,
        language=item.language,
        status=item.status,
        body=item.body,
        mentions=[
            MentionResponse(
                user_id=mention.user_id,
                start_utf16=mention.start_utf16,
                end_utf16=mention.end_utf16,
                display_text=mention.display_text,
            )
            for mention in item.mentions
        ],
        author=TranslationCommentAuthorResponse(
            id=item.author.id,
            display_name=item.author.display_name,
        ),
        current_version=item.current_version,
        edited=item.edited,
        created_at=item.created_at,
        updated_at=item.updated_at,
        deleted_at=item.deleted_at,
        deleted_by=item.deleted_by,
    )


def _page_response(page: TranslationCommentPage) -> TranslationCommentPageResponse:
    return TranslationCommentPageResponse(
        items=[_response(item) for item in page.items],
        older_cursor=page.older_cursor,
    )


def _anchor_response(window: CommentAnchorWindow) -> CommentAnchorWindowResponse:
    return CommentAnchorWindowResponse(
        target_id=window.target_id,
        items=[_response(item) for item in window.items],
    )


def _version_page_response(
    page: TranslationCommentVersionPage,
) -> TranslationCommentVersionPageResponse:
    return TranslationCommentVersionPageResponse(
        items=[
            TranslationCommentVersionResponse(
                version=item.version,
                status=item.status,
                body=item.body,
                mentions=[
                    MentionResponse(
                        user_id=mention.user_id,
                        start_utf16=mention.start_utf16,
                        end_utf16=mention.end_utf16,
                        display_text=mention.display_text,
                    )
                    for mention in item.mentions
                ],
                actor=TranslationCommentAuthorResponse(
                    id=item.actor.id,
                    display_name=item.actor.display_name,
                ),
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )


def _conflict_response(error: CommentVersionConflict) -> JSONResponse:
    payload = TranslationCommentConflictResponse(
        detail="Comment version conflict",
        attempted_body=error.attempted_body,
        attempted_version=error.attempted_version,
        latest=_response(error.latest),
    )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=payload.model_dump(mode="json"),
    )


async def _publish_after_commit(
    redis_client: NotificationRedisClient,
    *,
    recipient_ids: tuple[UUID, ...],
) -> None:
    """Publish only inserted recipients without changing the committed response."""
    try:
        if recipient_ids:
            await publish_notification_invalidations(
                redis_client,
                recipient_ids=recipient_ids,
            )
    except Exception:
        logger.warning("notification invalidation publication unavailable")


@router.post(
    "/{translation_group_id}/comments",
    operation_id="createTranslationComment",
    status_code=status.HTTP_201_CREATED,
    response_model=TranslationCommentResponse,
    responses=RESPONSES,
)
async def post_translation_comment(
    translation_group_id: UUID,
    payload: CreateTranslationCommentRequest,
    principal: CurrentPrincipal,
    session: CommentSession,
    redis_client: NotificationRedisDependency,
) -> TranslationCommentResponse:
    def save() -> tuple[TranslationCommentResponse, tuple[UUID, ...]]:
        try:
            result = create_translation_comment(
                session,
                principal=principal,
                translation_group_id=translation_group_id,
                body=payload.body,
                mentions=payload.mentions,
            )
            response = _response(result)
            session.commit()
            return response, result.new_notification_recipient_ids
        except Exception as error:
            session.rollback()
            _raise_comment_error(error)

    response, recipient_ids = await run_in_threadpool(save)
    await _publish_after_commit(
        redis_client,
        recipient_ids=recipient_ids,
    )
    return response


@router.get(
    "/{translation_group_id}/comments",
    operation_id="listTranslationComments",
    response_model=TranslationCommentPageResponse,
    responses=RESPONSES,
)
def get_translation_comments(
    translation_group_id: UUID,
    principal: CurrentPrincipal,
    session: CommentSession,
    settings: SettingsDependency,
    cursor: Annotated[CommentCursor | None, Query()] = None,
) -> TranslationCommentPageResponse:
    secret = settings.jwt_secret_key
    if secret is None:
        _raise_comment_error(RuntimeError("comment cursor signing unavailable"))
    try:
        return _page_response(
            list_translation_comments(
                session,
                principal=principal,
                translation_group_id=translation_group_id,
                cursor=cursor,
                cursor_secret=secret.get_secret_value(),
            )
        )
    except Exception as error:
        _raise_comment_error(error)


@router.get(
    "/{translation_group_id}/comments/anchor",
    operation_id="getTranslationCommentAnchor",
    response_model=CommentAnchorWindowResponse,
    responses=RESPONSES,
)
def get_translation_comment_window(
    translation_group_id: UUID,
    principal: CurrentPrincipal,
    session: CommentSession,
    comment: Annotated[UUID, Query()],
) -> CommentAnchorWindowResponse:
    try:
        return _anchor_response(
            get_translation_comment_anchor(
                session,
                principal=principal,
                translation_group_id=translation_group_id,
                comment_id=comment,
            )
        )
    except Exception as error:
        _raise_comment_error(error)


@router.put(
    "/{translation_group_id}/comments/{comment_id}",
    operation_id="updateTranslationComment",
    response_model=TranslationCommentResponse,
    responses=MUTATION_RESPONSES,
)
async def put_translation_comment(
    translation_group_id: UUID,
    comment_id: UUID,
    payload: UpdateTranslationCommentRequest,
    principal: CurrentPrincipal,
    session: CommentSession,
    redis_client: NotificationRedisDependency,
) -> TranslationCommentResponse | JSONResponse:
    def save() -> tuple[TranslationCommentResponse | JSONResponse, tuple[UUID, ...]]:
        try:
            result = edit_translation_comment(
                session,
                principal=principal,
                translation_group_id=translation_group_id,
                comment_id=comment_id,
                body=payload.body,
                expected_version=payload.expected_version,
                mentions=payload.mentions,
            )
            response = _response(result)
            session.commit()
            return response, result.new_notification_recipient_ids
        except CommentVersionConflict as error:
            session.rollback()
            return _conflict_response(error), ()
        except Exception as error:
            session.rollback()
            _raise_comment_error(error)

    response, recipient_ids = await run_in_threadpool(save)
    if isinstance(response, JSONResponse):
        return response
    await _publish_after_commit(
        redis_client,
        recipient_ids=recipient_ids,
    )
    return response


@router.delete(
    "/{translation_group_id}/comments/{comment_id}",
    operation_id="deleteTranslationComment",
    response_model=TranslationCommentResponse,
    responses=RESPONSES,
)
def remove_translation_comment(
    translation_group_id: UUID,
    comment_id: UUID,
    principal: CurrentPrincipal,
    session: CommentSession,
) -> TranslationCommentResponse:
    try:
        response = _response(
            delete_translation_comment(
                session,
                principal=principal,
                translation_group_id=translation_group_id,
                comment_id=comment_id,
            )
        )
        session.commit()
        return response
    except Exception as error:
        session.rollback()
        _raise_comment_error(error)


@router.get(
    "/{translation_group_id}/comments/{comment_id}/versions",
    operation_id="listTranslationCommentVersions",
    response_model=TranslationCommentVersionPageResponse,
    responses=RESPONSES,
)
def get_translation_comment_versions(
    translation_group_id: UUID,
    comment_id: UUID,
    principal: CurrentPrincipal,
    session: CommentSession,
    settings: SettingsDependency,
    cursor: Annotated[CommentCursor | None, Query()] = None,
) -> TranslationCommentVersionPageResponse:
    secret = settings.jwt_secret_key
    if secret is None:
        _raise_comment_error(RuntimeError("comment cursor signing unavailable"))
    try:
        return _version_page_response(
            list_comment_versions(
                session,
                principal=principal,
                translation_group_id=translation_group_id,
                comment_id=comment_id,
                cursor=cursor,
                cursor_secret=secret.get_secret_value(),
            )
        )
    except Exception as error:
        _raise_comment_error(error)
