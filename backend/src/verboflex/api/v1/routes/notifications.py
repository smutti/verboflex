"""Authenticated private notification REST routes."""

import logging
from typing import Annotated, Any, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.schemas.notifications import (
    NotificationActorResponse,
    NotificationErrorResponse,
    NotificationInvalidationEventResponse,
    NotificationItemResponse,
    NotificationPageResponse,
    NotificationProductResponse,
    NotificationReadResponse,
    NotificationUnreadCountResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.services.notifications import (
    InvalidNotificationCursor,
    NotificationItem,
    NotificationPage,
    NotificationReadResult,
    NotificationRedisClient,
    NotificationUnavailable,
    get_notification_redis_client,
    get_unread_notification_count,
    list_notifications,
    list_recent_notifications,
    mark_notification_read,
    mark_notification_read_by_comment,
    stream_notification_invalidations,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])
NotificationSession = Annotated[Session, Depends(get_db_session, use_cache=False)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
NotificationRedisDependency = Annotated[
    NotificationRedisClient, Depends(get_notification_redis_client)
]


class NotificationEventStreamResponse(StreamingResponse, JSONResponse):
    """Declare the stream media type so OpenAPI generation selects SSE transport."""

    media_type = "text/event-stream"


class NotificationListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view: Literal["all", "unread"] = "all"
    product_id: UUID | None = None
    cursor: Annotated[str | None, Query(min_length=1, max_length=2_048)] = None


RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": NotificationErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "content": {
            "application/json": {
                "schema": {
                    "anyOf": [
                        {"$ref": "#/components/schemas/NotificationErrorResponse"},
                        {"$ref": "#/components/schemas/HTTPValidationError"},
                    ]
                }
            }
        }
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": NotificationErrorResponse},
}


def _raise_notification_error(error: Exception) -> NoReturn:
    if isinstance(error, NotificationUnavailable):
        raise HTTPException(status_code=404, detail="Notification unavailable") from error
    if isinstance(error, InvalidNotificationCursor):
        raise HTTPException(status_code=422, detail="Invalid notification cursor") from error
    logger.exception("notification operation failed", exc_info=error)
    raise HTTPException(status_code=503, detail="Notification unavailable") from error


def _item_response(item: NotificationItem) -> NotificationItemResponse:
    return NotificationItemResponse(
        id=item.id,
        is_read=item.is_read,
        read_at=item.read_at,
        created_at=item.created_at,
        actor=NotificationActorResponse(
            user_id=item.actor.user_id,
            display_name=item.actor.display_name,
        ),
        product=NotificationProductResponse(id=item.product.id, name=item.product.name),
        key_excerpt=item.key_excerpt,
        language=item.language,
        translation_group_id=item.translation_group_id,
        originating_comment_id=item.originating_comment_id,
        comment_status=item.comment_status,
    )


def _page_response(page: NotificationPage) -> NotificationPageResponse:
    return NotificationPageResponse(
        items=[_item_response(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


def _read_response(result: NotificationReadResult) -> NotificationReadResponse:
    return NotificationReadResponse(
        item=_item_response(result.item),
        unread_count=result.unread_count,
    )


def _cursor_secret(settings: Settings) -> str:
    if settings.jwt_secret_key is None:
        _raise_notification_error(RuntimeError("notification cursor signing unavailable"))
    return settings.jwt_secret_key.get_secret_value()


@router.get(
    "/stream",
    operation_id="streamNotificationInvalidations",
    response_class=NotificationEventStreamResponse,
    response_model=NotificationInvalidationEventResponse,
    responses={
        status.HTTP_200_OK: {
            "model": NotificationInvalidationEventResponse,
            "content": {
                "text/event-stream": {
                    "schema": {
                        "$ref": ("#/components/schemas/NotificationInvalidationEventResponse")
                    }
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    },
)
async def get_notification_stream(
    request: Request,
    principal: CurrentPrincipal,
    redis_client: NotificationRedisDependency,
) -> NotificationEventStreamResponse:
    return NotificationEventStreamResponse(
        stream_notification_invalidations(
            redis_client,
            principal=principal,
            request=request,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store, no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "",
    operation_id="listNotifications",
    response_model=NotificationPageResponse,
    responses=RESPONSES,
)
async def get_notifications(
    principal: CurrentPrincipal,
    session: NotificationSession,
    settings: SettingsDependency,
    query: Annotated[NotificationListQuery, Query()],
) -> NotificationPageResponse:
    try:
        return _page_response(
            list_notifications(
                session,
                principal=principal,
                view=query.view,
                product_id=query.product_id,
                cursor=query.cursor,
                cursor_secret=_cursor_secret(settings),
            )
        )
    except Exception as error:
        _raise_notification_error(error)


@router.get(
    "/recent",
    operation_id="listRecentNotifications",
    response_model=NotificationPageResponse,
    responses=RESPONSES,
)
async def get_recent_notifications(
    principal: CurrentPrincipal,
    session: NotificationSession,
) -> NotificationPageResponse:
    try:
        return _page_response(list_recent_notifications(session, principal=principal))
    except Exception as error:
        _raise_notification_error(error)


@router.get(
    "/unread-count",
    operation_id="getUnreadNotificationCount",
    response_model=NotificationUnreadCountResponse,
    responses=RESPONSES,
)
async def get_notification_count(
    principal: CurrentPrincipal,
    session: NotificationSession,
) -> NotificationUnreadCountResponse:
    try:
        return NotificationUnreadCountResponse(
            unread_count=get_unread_notification_count(session, principal=principal)
        )
    except Exception as error:
        _raise_notification_error(error)


@router.post(
    "/by-comment/{comment_id}/read",
    operation_id="markNotificationReadByComment",
    response_model=NotificationReadResponse,
    responses=RESPONSES,
)
async def post_notification_read_by_comment(
    comment_id: UUID,
    principal: CurrentPrincipal,
    session: NotificationSession,
) -> NotificationReadResponse:
    try:
        response = _read_response(
            mark_notification_read_by_comment(
                session,
                principal=principal,
                comment_id=comment_id,
            )
        )
        session.commit()
        return response
    except Exception as error:
        session.rollback()
        _raise_notification_error(error)


@router.post(
    "/{notification_id}/read",
    operation_id="markNotificationRead",
    response_model=NotificationReadResponse,
    responses=RESPONSES,
)
async def post_notification_read(
    notification_id: UUID,
    principal: CurrentPrincipal,
    session: NotificationSession,
) -> NotificationReadResponse:
    try:
        response = _read_response(
            mark_notification_read(
                session,
                principal=principal,
                notification_id=notification_id,
            )
        )
        session.commit()
        return response
    except Exception as error:
        session.rollback()
        _raise_notification_error(error)
