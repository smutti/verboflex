"""Private durable notification HTTP contracts."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import ModuleType
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session, sessionmaker

from verboflex.auth.access_tokens import decode_access_token
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.review import Notification, TranslationComment
from verboflex.models.user import User


def _support() -> ModuleType:
    return importlib.import_module("tests.api.test_translation_reviews")


SUPPORT = _support()
PATH = "/api/v1/notifications"


def _require_contract() -> None:
    required = {
        "verboflex.schemas.notifications": (
            "NotificationActorResponse",
            "NotificationProductResponse",
            "NotificationItemResponse",
            "NotificationPageResponse",
            "NotificationReadResponse",
            "NotificationCommentStatus",
        ),
        "verboflex.services.notifications": (
            "list_notifications",
            "list_recent_notifications",
            "get_unread_notification_count",
            "mark_notification_read",
            "mark_notification_read_by_comment",
            "stream_notification_invalidations",
            "publish_notification_invalidations",
        ),
    }
    for module_name, symbols in required.items():
        assert importlib.util.find_spec(module_name) is not None, f"missing {module_name}"
        module = importlib.import_module(module_name)
        assert not (set(symbols) - set(dir(module)))
    paths = app.openapi()["paths"]
    assert paths[PATH]["get"]["operationId"] == "listNotifications"
    assert paths[f"{PATH}/recent"]["get"]["operationId"] == "listRecentNotifications"
    assert paths[f"{PATH}/unread-count"]["get"]["operationId"] == "getUnreadNotificationCount"
    assert (
        paths[f"{PATH}/{{notification_id}}/read"]["post"]["operationId"] == "markNotificationRead"
    )
    assert (
        paths[f"{PATH}/by-comment/{{comment_id}}/read"]["post"]["operationId"]
        == "markNotificationReadByComment"
    )
    stream = paths[f"{PATH}/stream"]["get"]
    assert stream["operationId"] == "streamNotificationInvalidations"
    assert stream["security"] == [{"OAuth2PasswordBearer": []}]


@pytest.fixture(scope="module")
def notification_factory() -> Iterator[sessionmaker[Session]]:
    with SUPPORT._review_database() as factory:
        yield factory


@pytest.fixture(autouse=True)
def clean_database(notification_factory: sessionmaker[Session]) -> Iterator[None]:
    app.dependency_overrides.clear()
    with notification_factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories CASCADE"))
        session.execute(delete(AuthSession))
        session.execute(delete(User))
    yield
    app.dependency_overrides.clear()


async def _request(
    method: str,
    path: str,
    *,
    token: str | None,
    params: dict[str, object] | None = None,
):
    import httpx

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    headers = {"Authorization": f"Bearer {token}"} if token else None
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, headers=headers, params=params)


def _authority(factory: sessionmaker[Session], role: str = "viewer") -> tuple[str, UUID]:
    token = SUPPORT.SUPPORT._create_authority(factory, role_names=(role,))
    user_id = decode_access_token(token, settings=SUPPORT.SUPPORT._settings()).user_id
    return token, user_id


def _seed_notification(
    factory: sessionmaker[Session],
    *,
    ids: dict[str, object],
    actor_id: UUID,
    recipient_id: UUID,
    created_at: datetime,
    notification_id: UUID | None = None,
    deleted: bool = False,
    read_at: datetime | None = None,
) -> tuple[UUID, UUID]:
    with factory.begin() as session:
        comment = TranslationComment(
            scope_id=ids["scope"],
            translation_key_id=ids["key"],
            language="it",
            author_id=actor_id,
            current_version=1,
            created_at=created_at,
            updated_at=created_at,
            deleted_at=created_at if deleted else None,
            deleted_by=actor_id if deleted else None,
        )
        session.add(comment)
        session.flush()
        notification = Notification(
            id=notification_id or uuid4(),
            recipient_user_id=recipient_id,
            actor_user_id=actor_id,
            originating_comment_id=comment.id,
            kind="mention",
            created_at=created_at,
            read_at=read_at,
        )
        session.add(notification)
        return notification.id, comment.id


def _assert_closed_item(item: dict[str, object], *, ids: dict[str, object]) -> None:
    assert set(item) == {
        "id",
        "is_read",
        "read_at",
        "created_at",
        "actor",
        "product",
        "key_excerpt",
        "language",
        "translation_group_id",
        "originating_comment_id",
        "comment_status",
    }
    assert set(item["actor"]) == {"user_id", "display_name"}
    assert set(item["product"]) == {"id", "name"}
    assert item["product"]["id"] == str(ids["product"])
    assert item["language"] == "it"
    assert item["translation_group_id"] == str(ids["group"])
    forbidden = {
        "recipient",
        "recipient_id",
        "body",
        "email",
        "roles",
        "repository",
        "provider",
        "path",
        "token",
        "sql",
        "exception",
    }

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(child) for child in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(child) for child in value))
        return set()

    assert not (keys(item) & forbidden)


def test_notification_contract_is_closed_registered_and_principal_only() -> None:
    _require_contract()
    schemas = importlib.import_module("verboflex.schemas.notifications")
    assert schemas.NotificationItemResponse.model_config["extra"] == "forbid"
    service = importlib.import_module("verboflex.services.notifications")
    for name in (
        "list_notifications",
        "list_recent_notifications",
        "get_unread_notification_count",
        "mark_notification_read",
        "mark_notification_read_by_comment",
        "stream_notification_invalidations",
    ):
        parameters = importlib.import_module("inspect").signature(getattr(service, name)).parameters
        assert "principal" in parameters
        assert "recipient" not in parameters
        assert "recipient_id" not in parameters

    stream = asyncio.run(_request("GET", f"{PATH}/stream", token=None))
    assert stream.status_code == 401


def test_list_recent_count_filters_and_closed_projection_are_private(
    notification_factory: sessionmaker[Session],
) -> None:
    _require_contract()
    ids = SUPPORT._seed_scalar_basis(notification_factory, name="Private notifications")
    actor_token, actor_id = _authority(notification_factory, "translator")
    recipient_token, recipient_id = _authority(notification_factory)
    foreign_token, foreign_id = _authority(notification_factory)
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    own_id, own_comment = _seed_notification(
        notification_factory,
        ids=ids,
        actor_id=actor_id,
        recipient_id=recipient_id,
        created_at=now,
    )
    _seed_notification(
        notification_factory,
        ids=ids,
        actor_id=actor_id,
        recipient_id=foreign_id,
        created_at=now + timedelta(seconds=1),
    )
    SUPPORT.SUPPORT._configure_dependencies(notification_factory)

    anonymous = asyncio.run(_request("GET", PATH, token=None))
    assert anonymous.status_code == 401
    page = asyncio.run(_request("GET", PATH, token=recipient_token))
    assert page.status_code == 200
    assert page.json()["next_cursor"] is None
    assert len(page.json()["items"]) == 1
    item = page.json()["items"][0]
    _assert_closed_item(item, ids=ids)
    assert item["id"] == str(own_id)
    assert item["originating_comment_id"] == str(own_comment)
    assert item["is_read"] is False and item["read_at"] is None
    assert item["comment_status"] == "available"
    assert item["actor"]["user_id"] == str(actor_id)
    assert item["key_excerpt"]

    recent = asyncio.run(_request("GET", f"{PATH}/recent", token=recipient_token))
    assert recent.status_code == 200
    assert recent.json() == page.json()
    count = asyncio.run(_request("GET", f"{PATH}/unread-count", token=recipient_token))
    assert count.status_code == 200
    assert count.json() == {"unread_count": 1}
    assert type(count.json()["unread_count"]) is int
    assert (
        asyncio.run(_request("GET", PATH, token=foreign_token)).json()["items"]
        != page.json()["items"]
    )
    assert asyncio.run(
        _request(
            "GET",
            PATH,
            token=recipient_token,
            params={"view": "unread", "product_id": str(ids["product"])},
        )
    ).json()["items"] == [item]
    # Reading a collection is inert.
    with notification_factory() as session:
        assert session.get_one(Notification, own_id).read_at is None
    assert actor_token  # The actor token is deliberately never notification authority.


def test_manual_and_origin_reads_are_idempotent_and_never_cross_recipient(
    notification_factory: sessionmaker[Session],
) -> None:
    ids = SUPPORT._seed_scalar_basis(notification_factory, name="Read notification")
    _actor_token, actor_id = _authority(notification_factory, "translator")
    own_token, own_user = _authority(notification_factory)
    foreign_token, foreign_user = _authority(notification_factory)
    notification_id, comment_id = _seed_notification(
        notification_factory,
        ids=ids,
        actor_id=actor_id,
        recipient_id=own_user,
        created_at=datetime.now(UTC),
    )
    SUPPORT.SUPPORT._configure_dependencies(notification_factory)

    for token, path in (
        (foreign_token, f"{PATH}/{notification_id}/read"),
        (foreign_token, f"{PATH}/by-comment/{comment_id}/read"),
        (own_token, f"{PATH}/{uuid4()}/read"),
        (own_token, f"{PATH}/by-comment/{uuid4()}/read"),
    ):
        response = asyncio.run(_request("POST", path, token=token))
        assert response.status_code == 404
        assert response.json() == {"detail": "Notification unavailable"}
    with notification_factory() as session:
        assert session.get_one(Notification, notification_id).read_at is None

    first = asyncio.run(_request("POST", f"{PATH}/{notification_id}/read", token=own_token))
    assert first.status_code == 200
    _assert_closed_item(first.json()["item"], ids=ids)
    assert first.json()["item"]["is_read"] is True
    assert first.json()["item"]["read_at"] is not None
    assert first.json()["unread_count"] == 0
    repeated = asyncio.run(_request("POST", f"{PATH}/{notification_id}/read", token=own_token))
    assert repeated.status_code == 200
    assert repeated.json() == first.json()
    by_comment = asyncio.run(
        _request("POST", f"{PATH}/by-comment/{comment_id}/read", token=own_token)
    )
    assert by_comment.status_code == 200
    assert by_comment.json() == first.json()
    with notification_factory() as session:
        assert (
            session.scalar(
                select(Notification.read_at).where(Notification.recipient_user_id == foreign_user)
            )
            is None
        )


def test_equal_timestamp_keyset_is_stable_and_cursor_is_bound(
    notification_factory: sessionmaker[Session],
) -> None:
    ids = SUPPORT._seed_scalar_basis(notification_factory, name="Cursor notification")
    _actor_token, actor_id = _authority(notification_factory, "translator")
    token, user_id = _authority(notification_factory)
    same_time = datetime(2026, 9, 10, 13, 0, tzinfo=UTC)
    expected_ids: list[UUID] = []
    for index in range(26):
        notification_id = UUID(int=index + 1)
        expected_ids.append(notification_id)
        _seed_notification(
            notification_factory,
            ids=ids,
            actor_id=actor_id,
            recipient_id=user_id,
            created_at=same_time,
            notification_id=notification_id,
        )
    SUPPORT.SUPPORT._configure_dependencies(notification_factory)
    first = asyncio.run(_request("GET", PATH, token=token))
    assert first.status_code == 200
    assert [UUID(item["id"]) for item in first.json()["items"]] == sorted(
        expected_ids, reverse=True
    )[:25]
    cursor = first.json()["next_cursor"]
    assert cursor
    second = asyncio.run(_request("GET", PATH, token=token, params={"cursor": cursor}))
    assert [UUID(item["id"]) for item in second.json()["items"]] == [min(expected_ids)]
    for other_params in (
        {"cursor": cursor, "view": "unread"},
        {"cursor": cursor, "product_id": str(uuid4())},
        {"cursor": "tampered"},
    ):
        invalid = asyncio.run(_request("GET", PATH, token=token, params=other_params))
        assert invalid.status_code in (404, 422)
    other_token, _other_id = _authority(notification_factory)
    SUPPORT.SUPPORT._configure_dependencies(notification_factory)
    replay = asyncio.run(_request("GET", PATH, token=other_token, params={"cursor": cursor}))
    assert replay.status_code == 422


def test_deleted_comment_is_linkable_without_body(
    notification_factory: sessionmaker[Session],
) -> None:
    ids = SUPPORT._seed_scalar_basis(notification_factory, name="Removed comment")
    _actor_token, actor_id = _authority(notification_factory, "translator")
    token, user_id = _authority(notification_factory)
    notification_id, _comment_id = _seed_notification(
        notification_factory,
        ids=ids,
        actor_id=actor_id,
        recipient_id=user_id,
        created_at=datetime.now(UTC),
        deleted=True,
    )
    SUPPORT.SUPPORT._configure_dependencies(notification_factory)
    response = asyncio.run(_request("GET", PATH, token=token))
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == str(notification_id)
    assert item["comment_status"] == "removed"
    assert "body" not in item


def test_invalid_or_inaccessible_product_is_generically_unavailable(
    notification_factory: sessionmaker[Session],
) -> None:
    active = SUPPORT._seed_scalar_basis(notification_factory, name="Visible product")
    inactive = SUPPORT._seed_scalar_basis(
        notification_factory, name="Inactive product", active=False
    )
    token, _user_id = _authority(notification_factory)
    SUPPORT.SUPPORT._configure_dependencies(notification_factory)
    for product_id in (uuid4(), inactive["product"]):
        response = asyncio.run(
            _request("GET", PATH, token=token, params={"product_id": str(product_id)})
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Notification unavailable"}
    assert active["product"] != inactive["product"]
