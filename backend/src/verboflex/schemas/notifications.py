"""Closed public contracts for personal mention notifications."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from verboflex.schemas.translations import LanguageCode

type NotificationCommentStatus = Literal["available", "removed"]
NotificationCursor = Annotated[str, Field(min_length=1, max_length=2_048)]


class ClosedNotificationModel(BaseModel):
    """Reject accidental authority or provider fields at the HTTP boundary."""

    model_config = ConfigDict(extra="forbid")


class NotificationActorResponse(ClosedNotificationModel):
    user_id: UUID
    display_name: Annotated[str, Field(min_length=1, max_length=200)]


class NotificationProductResponse(ClosedNotificationModel):
    id: UUID
    name: Annotated[str, Field(min_length=1, max_length=200)]


class NotificationItemResponse(ClosedNotificationModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "unread",
                    "value": {
                        "id": "11111111-1111-4111-8111-111111111111",
                        "is_read": False,
                        "created_at": "2026-09-10T12:00:00Z",
                        "actor": {
                            "user_id": "22222222-2222-4222-8222-222222222222",
                            "display_name": "Ada Reviewer",
                        },
                        "product": {
                            "id": "33333333-3333-4333-8333-333333333333",
                            "name": "Example product",
                        },
                        "key_excerpt": "account.save",
                        "language": "it",
                        "translation_group_id": ("44444444-4444-4444-8444-444444444444"),
                        "originating_comment_id": ("55555555-5555-4555-8555-555555555555"),
                        "comment_status": "available",
                    },
                },
                {
                    "name": "read",
                    "value": {
                        "id": "11111111-1111-4111-8111-111111111111",
                        "is_read": True,
                        "read_at": "2026-09-10T12:05:00Z",
                        "created_at": "2026-09-10T12:00:00Z",
                        "actor": {
                            "user_id": "22222222-2222-4222-8222-222222222222",
                            "display_name": "Ada Reviewer",
                        },
                        "product": {
                            "id": "33333333-3333-4333-8333-333333333333",
                            "name": "Example product",
                        },
                        "key_excerpt": "account.save",
                        "language": "it",
                        "translation_group_id": ("44444444-4444-4444-8444-444444444444"),
                        "originating_comment_id": ("55555555-5555-4555-8555-555555555555"),
                        "comment_status": "available",
                    },
                },
                {
                    "name": "removed",
                    "value": {
                        "id": "11111111-1111-4111-8111-111111111111",
                        "is_read": False,
                        "created_at": "2026-09-10T12:00:00Z",
                        "actor": {
                            "user_id": "22222222-2222-4222-8222-222222222222",
                            "display_name": "Ada Reviewer",
                        },
                        "product": {
                            "id": "33333333-3333-4333-8333-333333333333",
                            "name": "Example product",
                        },
                        "key_excerpt": "account.save",
                        "language": "it",
                        "translation_group_id": ("44444444-4444-4444-8444-444444444444"),
                        "originating_comment_id": ("55555555-5555-4555-8555-555555555555"),
                        "comment_status": "removed",
                    },
                },
            ]
        },
    )

    id: UUID
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime
    actor: NotificationActorResponse
    product: NotificationProductResponse
    key_excerpt: Annotated[str, Field(min_length=1, max_length=200)]
    language: LanguageCode
    translation_group_id: UUID
    originating_comment_id: UUID
    comment_status: NotificationCommentStatus


class NotificationPageResponse(ClosedNotificationModel):
    items: Annotated[list[NotificationItemResponse], Field(max_length=25)]
    next_cursor: NotificationCursor | None


class NotificationUnreadCountResponse(ClosedNotificationModel):
    unread_count: Annotated[int, Field(strict=True, ge=0)]


class NotificationReadResponse(NotificationUnreadCountResponse):
    item: NotificationItemResponse


class NotificationErrorResponse(ClosedNotificationModel):
    detail: Literal[
        "Notification unavailable",
        "Invalid notification cursor",
    ]


class NotificationInvalidationEventResponse(ClosedNotificationModel):
    """Content-free stream signal; clients refetch personal state over REST."""

    id: Annotated[str, Field(pattern=r"^[1-9][0-9]{0,63}$")]
    kind: Literal["notifications_changed"]
