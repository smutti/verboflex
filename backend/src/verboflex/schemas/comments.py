"""Closed public contracts for stable translation discussions."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from verboflex.core.text import StorableText
from verboflex.schemas.translations import LanguageCode

CommentBody = Annotated[StorableText, Field(min_length=1, max_length=65_536)]
CommentVersion = Annotated[StrictInt, Field(ge=1, le=9_007_199_254_740_991)]
CommentCursor = Annotated[str, Field(min_length=1, max_length=2_048)]


class ClosedCommentModel(BaseModel):
    """Reject accidental discussion fields at the HTTP boundary."""

    model_config = ConfigDict(extra="forbid")


class MentionInput(ClosedCommentModel):
    """One immutable-user selection expressed in browser UTF-16 coordinates."""

    user_id: UUID
    start_utf16: StrictInt
    end_utf16: StrictInt
    display_text: Annotated[str, Field(min_length=2, max_length=201)]


class MentionResponse(MentionInput):
    """Validated historical rendering evidence for a structured mention."""


class CreateTranslationCommentRequest(ClosedCommentModel):
    body: CommentBody
    mentions: Annotated[list[MentionInput], Field(max_length=32_768)] = Field(default_factory=list)

    @field_validator("body")
    @classmethod
    def require_nonblank_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("comment body must contain non-whitespace text")
        return value


class UpdateTranslationCommentRequest(CreateTranslationCommentRequest):
    expected_version: CommentVersion


class TranslationCommentAuthorResponse(ClosedCommentModel):
    id: UUID
    display_name: Annotated[str, Field(min_length=1, max_length=200)]


class TranslationCommentResponse(ClosedCommentModel):
    id: UUID
    translation_group_id: UUID
    language: LanguageCode
    status: Literal["available", "removed"]
    body: CommentBody | None
    mentions: list[MentionResponse]
    author: TranslationCommentAuthorResponse
    current_version: CommentVersion
    edited: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    deleted_by: UUID | None


class TranslationCommentPageResponse(ClosedCommentModel):
    items: Annotated[list[TranslationCommentResponse], Field(max_length=5)]
    older_cursor: CommentCursor | None


class CommentAnchorWindowResponse(ClosedCommentModel):
    target_id: UUID
    items: Annotated[
        list[TranslationCommentResponse],
        Field(min_length=1, max_length=11),
    ]


class TranslationCommentVersionResponse(ClosedCommentModel):
    version: CommentVersion
    status: Literal["available", "removed"]
    body: CommentBody | None
    mentions: list[MentionResponse]
    actor: TranslationCommentAuthorResponse
    created_at: datetime


class TranslationCommentVersionPageResponse(ClosedCommentModel):
    items: Annotated[list[TranslationCommentVersionResponse], Field(max_length=50)]
    next_cursor: CommentCursor | None


class TranslationCommentErrorResponse(ClosedCommentModel):
    detail: Literal[
        "Comment unavailable",
        "Comment action denied",
        "Invalid comment input",
        "Invalid comment cursor",
        "Comment version conflict",
    ]


class TranslationCommentConflictResponse(ClosedCommentModel):
    detail: Literal["Comment version conflict"]
    attempted_body: CommentBody
    attempted_version: CommentVersion
    latest: TranslationCommentResponse
