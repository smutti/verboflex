"""Close fail-safe Phase 5 route branches without weakening public errors."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from verboflex.api.v1.routes import (
    comments,
    notifications,
    translation_reviews,
    translations,
    users,
)
from verboflex.auth.principal import Principal
from verboflex.auth.translation_access import TranslationGroupActionDenied
from verboflex.schemas.reviews import ReviewTransitionRequest
from verboflex.schemas.users import RoleName
from verboflex.services.translation_reviews import (
    ProposalVersionConflict,
    TranslationProposalComparison,
)


class TransactionProbe:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _principal() -> Principal:
    return Principal(
        user_id=uuid4(),
        email="phase5@example.com",
        display_name="Phase Five",
        roles=(RoleName.ADMIN,),
        must_change_password=False,
    )


@pytest.mark.parametrize(
    ("raiser", "expected_status"),
    [
        (comments._raise_comment_error, 503),
        (notifications._raise_notification_error, 503),
        (translation_reviews._raise_proposal_error, 503),
    ],
)
def test_unknown_route_failures_are_logged_and_closed(raiser, expected_status: int) -> None:
    with pytest.raises(HTTPException) as captured:
        raiser(RuntimeError("private failure detail"))
    assert captured.value.status_code == expected_status
    assert "private failure detail" not in str(captured.value.detail)


def test_missing_cursor_secrets_fail_closed_before_service_access() -> None:
    principal = _principal()
    unsigned = SimpleNamespace(jwt_secret_key=None)
    for call in (
        lambda: comments.get_translation_comments(uuid4(), principal, object(), unsigned),
        lambda: comments.get_translation_comment_versions(
            uuid4(), uuid4(), principal, object(), unsigned
        ),
        lambda: translation_reviews.get_translation_review_activity(
            uuid4(), principal, object(), unsigned
        ),
    ):
        with pytest.raises(HTTPException) as captured:
            call()
        assert captured.value.status_code == 503

    with pytest.raises(HTTPException) as captured:
        notifications._cursor_secret(unsigned)
    assert captured.value.status_code == 503


def test_notification_stream_route_sets_non_buffering_no_store_headers() -> None:
    response = asyncio.run(notifications.get_notification_stream(object(), _principal(), object()))
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-store, no-cache"
    assert response.headers["x-accel-buffering"] == "no"


@pytest.mark.parametrize(
    ("route_name", "service_name"),
    [
        ("get_recent_notifications", "list_recent_notifications"),
        ("get_notification_count", "get_unread_notification_count"),
    ],
)
def test_notification_read_routes_translate_unexpected_service_errors(
    monkeypatch: pytest.MonkeyPatch, route_name: str, service_name: str
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("database details")

    monkeypatch.setattr(notifications, service_name, fail)
    with pytest.raises(HTTPException) as captured:
        asyncio.run(getattr(notifications, route_name)(_principal(), object()))
    assert captured.value.status_code == 503


def test_comment_history_route_translates_late_service_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("database details")

    monkeypatch.setattr(comments, "list_comment_versions", fail)
    settings = SimpleNamespace(jwt_secret_key=SecretStr("test-signing-key"))
    with pytest.raises(HTTPException) as captured:
        comments.get_translation_comment_versions(
            uuid4(), uuid4(), _principal(), object(), settings
        )
    assert captured.value.status_code == 503


def test_transition_conflict_without_latest_authority_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = TransactionProbe()

    def conflict(*_args: object, **_kwargs: object) -> None:
        raise ProposalVersionConflict(
            TranslationProposalComparison(
                attempted_version=7,
                attempted_values=(),
                latest=None,
            )
        )

    monkeypatch.setattr(translation_reviews, "transition_translation_proposal", conflict)
    with pytest.raises(HTTPException) as captured:
        translation_reviews.post_translation_proposal_state(
            uuid4(),
            ReviewTransitionRequest(target_state="approved", expected_version=7),
            _principal(),
            session,
        )
    assert captured.value.status_code == 404
    assert session.rollbacks == 1


def test_activity_value_projection_preserves_explicit_absence() -> None:
    assert translation_reviews._activity_values(None) is None


def test_translation_detail_maps_action_denial_to_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny(*_args: object, **_kwargs: object) -> None:
        raise TranslationGroupActionDenied("denied")

    monkeypatch.setattr(translations, "resolve_translation_group_access", deny)
    with pytest.raises(HTTPException) as captured:
        translations.get_translation_group_detail(uuid4(), _principal(), object())
    assert captured.value.status_code == 403


def test_mention_search_treats_whitespace_as_no_query_without_database_access() -> None:
    assert asyncio.run(users.search_mention_users(_principal(), object(), "   ")) == []
