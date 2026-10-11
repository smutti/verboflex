"""Private, content-free, post-commit notification invalidation contracts."""

from __future__ import annotations

import asyncio
import importlib
import json
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from types import ModuleType
from uuid import UUID, uuid4

import httpx
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from verboflex.api.v1.routes import comments as comment_routes
from verboflex.auth.access_tokens import decode_access_token
from verboflex.auth.passwords import hash_password
from verboflex.auth.principal import Principal
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.review import Notification
from verboflex.models.user import User
from verboflex.schemas.users import RoleName


def _support() -> ModuleType:
    return importlib.import_module("tests.api.test_translation_reviews")


SUPPORT = _support()


@dataclass
class FakeBroker:
    counters: dict[str, int] = field(default_factory=dict)
    messages: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    publications: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class FakePubSub:
    broker: FakeBroker
    channel: str | None = None
    unsubscribed: bool = False
    closed: bool = False

    async def subscribe(self, channel: str) -> None:
        self.channel = channel

    async def get_message(
        self,
        *,
        ignore_subscribe_messages: bool,
        timeout: float,
    ) -> dict[str, object] | None:
        assert ignore_subscribe_messages is True
        assert timeout > 0
        assert self.channel is not None
        queued = self.broker.messages.setdefault(self.channel, [])
        return queued.pop(0) if queued else None

    async def unsubscribe(self, channel: str) -> None:
        assert channel == self.channel
        self.unsubscribed = True

    async def aclose(self) -> None:
        self.closed = True


@dataclass
class FakeRedis:
    broker: FakeBroker
    pubsub_instance: FakePubSub | None = None
    closed: bool = False

    async def incr(self, key: str) -> int:
        value = self.broker.counters.get(key, 0) + 1
        self.broker.counters[key] = value
        return value

    async def publish(self, channel: str, payload: str) -> int:
        self.broker.publications.append((channel, payload))
        self.broker.messages.setdefault(channel, []).append(
            {"type": "message", "channel": channel, "data": payload}
        )
        return 1

    def pubsub(self) -> FakePubSub:
        self.pubsub_instance = FakePubSub(self.broker)
        return self.pubsub_instance

    async def aclose(self) -> None:
        self.closed = True


@dataclass
class FakeRequest:
    states: list[bool]

    async def is_disconnected(self) -> bool:
        return self.states.pop(0) if self.states else True


def _principal(value: int) -> Principal:
    return Principal(
        user_id=UUID(int=value),
        email=f"person-{value}@example.com",
        display_name=f"Person {value}",
        roles=(RoleName.VIEWER,),
        must_change_password=False,
    )


async def _collect(stream: AsyncIterator[str]) -> list[str]:
    return [frame async for frame in stream]


def test_two_principals_receive_only_closed_own_channel_frames_and_heartbeat() -> None:
    service = importlib.import_module("verboflex.services.notifications")
    broker = FakeBroker()
    publisher = FakeRedis(broker)
    first = _principal(1001)
    second = _principal(1002)

    asyncio.run(
        service.publish_notification_invalidations(
            publisher,
            recipient_ids=(first.user_id, second.user_id),
        )
    )
    asyncio.run(
        service.publish_notification_invalidations(
            publisher,
            recipient_ids=(first.user_id,),
        )
    )
    assert len(broker.publications) == 3
    channels = [channel for channel, _payload in broker.publications]
    assert len(set(channels)) == 2
    assert all(str(first.user_id) not in channel for channel in channels)
    assert all(str(second.user_id) not in channel for channel in channels)
    published_events = [json.loads(raw_payload) for _channel, raw_payload in broker.publications]
    for parsed in published_events:
        assert set(parsed) == {"kind", "id"}
        assert parsed["kind"] == "notifications_changed"
        assert isinstance(parsed["id"], str) and parsed["id"]

    first_client = FakeRedis(broker)
    first_frames = asyncio.run(
        _collect(
            service.stream_notification_invalidations(
                first_client,
                principal=first,
                request=FakeRequest([False, False, False, True]),
                heartbeat_seconds=0.01,
            )
        )
    )
    assert first_frames[0] == "retry: 5000\n\n"
    event_frame = first_frames[1]
    assert "event: notification-invalidation\n" in event_frame
    data_line = next(line for line in event_frame.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))
    assert set(payload) == {"kind", "id"}
    forbidden = (
        "recipient",
        "count",
        "actor",
        "product",
        "key",
        "language",
        "comment",
        "body",
        "reason",
        "display",
    )
    assert not any(word in event_frame.casefold() for word in forbidden)
    second_event_data = next(
        line for line in first_frames[2].splitlines() if line.startswith("data: ")
    )
    assert int(json.loads(second_event_data.removeprefix("data: "))["id"]) > int(payload["id"])
    assert first_frames[3] == ": heartbeat\n\n"
    assert first_client.pubsub_instance is not None
    assert first_client.pubsub_instance.unsubscribed is True
    assert first_client.pubsub_instance.closed is True
    assert first_client.closed is True

    second_client = FakeRedis(broker)
    second_frames = asyncio.run(
        _collect(
            service.stream_notification_invalidations(
                second_client,
                principal=second,
                request=FakeRequest([False, True]),
                heartbeat_seconds=0.01,
            )
        )
    )
    second_data = next(line for line in second_frames[1].splitlines() if line.startswith("data: "))
    assert json.loads(second_data.removeprefix("data: ")) == published_events[1]


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff",
        42,
        "x" * 257,
        "not-json",
        "[]",
        '{"kind":"notifications_changed"}',
        '{"id":"1","kind":"other"}',
        '{"id":1,"kind":"notifications_changed"}',
        '{"id":"0","kind":"notifications_changed"}',
    ],
)
def test_notification_invalidation_decoder_rejects_every_open_or_invalid_shape(
    payload: object,
) -> None:
    service = importlib.import_module("verboflex.services.notifications")
    assert service._decode_invalidation(payload) is None


def test_notification_publish_rejects_non_integer_sequence() -> None:
    service = importlib.import_module("verboflex.services.notifications")

    class InvalidSequenceRedis(FakeRedis):
        async def incr(self, key: str) -> bool:
            del key
            return True

    with pytest.raises(RuntimeError, match="sequence unavailable"):
        asyncio.run(
            service.publish_notification_invalidations(
                InvalidSequenceRedis(FakeBroker()),
                recipient_ids=(_principal(1003).user_id,),
            )
        )


def test_notification_stream_rejects_invalid_heartbeat_and_skips_non_messages() -> None:
    service = importlib.import_module("verboflex.services.notifications")
    principal = _principal(1004)
    broker = FakeBroker()
    client = FakeRedis(broker)
    with pytest.raises(ValueError, match="heartbeat"):
        asyncio.run(
            _collect(
                service.stream_notification_invalidations(
                    client,
                    principal=principal,
                    request=FakeRequest([False]),
                    heartbeat_seconds=0,
                )
            )
        )

    channel = service._notification_channel(principal.user_id)
    broker.messages[channel] = [
        {"type": "subscribe", "data": "ignored"},
        {"type": "message", "data": "not-json"},
    ]
    frames = asyncio.run(
        _collect(
            service.stream_notification_invalidations(
                client,
                principal=principal,
                request=FakeRequest([False, False, True]),
                heartbeat_seconds=0.01,
            )
        )
    )
    assert frames == ["retry: 5000\n\n"]


def test_notification_stream_degrades_to_content_free_heartbeat_on_redis_error() -> None:
    service = importlib.import_module("verboflex.services.notifications")

    class FailingPubSub(FakePubSub):
        async def get_message(self, *, ignore_subscribe_messages: bool, timeout: float):
            del ignore_subscribe_messages, timeout
            raise RedisConnectionError("broker unavailable")

    class FailingRedis(FakeRedis):
        def pubsub(self) -> FakePubSub:
            self.pubsub_instance = FailingPubSub(self.broker)
            return self.pubsub_instance

    frames = asyncio.run(
        _collect(
            service.stream_notification_invalidations(
                FailingRedis(FakeBroker()),
                principal=_principal(1005),
                request=FakeRequest([False]),
                heartbeat_seconds=0.01,
            )
        )
    )
    assert frames == ["retry: 5000\n\n", ": heartbeat\n\n"]


@pytest.fixture(scope="module")
def notification_stream_factory() -> Iterator[sessionmaker[Session]]:
    with SUPPORT._review_database() as factory:
        yield factory


@pytest.fixture(autouse=True)
def clean_database(
    notification_stream_factory: sessionmaker[Session],
) -> Iterator[None]:
    app.dependency_overrides.clear()
    with notification_stream_factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories CASCADE"))
        session.execute(delete(AuthSession))
        session.execute(delete(User))
    yield
    app.dependency_overrides.clear()


async def _post_comment(
    group_id: object,
    *,
    token: str,
    payload: dict[str, object],
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            f"/api/v1/translations/{group_id}/comments",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )


def _comment_authority(
    factory: sessionmaker[Session],
) -> tuple[dict[str, object], str, UUID, UUID]:
    ids = SUPPORT._seed_scalar_basis(factory, name="Post commit invalidation")
    token = SUPPORT.SUPPORT._create_authority(factory, role_names=("translator",))
    actor_id = decode_access_token(token, settings=SUPPORT.SUPPORT._settings()).user_id
    recipient_id = uuid4()
    with factory.begin() as session:
        session.add(
            User(
                id=recipient_id,
                email="stream-recipient@example.com",
                display_name="Stream Recipient",
                hashed_password=hash_password("stream recipient password!"),
                is_active=True,
                must_change_password=False,
            )
        )
    SUPPORT.SUPPORT._configure_dependencies(factory)
    return ids, token, actor_id, recipient_id


def _mention_payload(recipient_id: UUID) -> dict[str, object]:
    visible = "@Stream Recipient"
    return {
        "body": f"Please check {visible}",
        "mentions": [
            {
                "user_id": str(recipient_id),
                "start_utf16": len("Please check "),
                "end_utf16": len("Please check ") + len(visible),
                "display_text": visible,
            }
        ],
    }


def test_comment_commit_precedes_publish_and_rollback_publishes_nothing(
    notification_stream_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids, token, _actor_id, recipient_id = _comment_authority(notification_stream_factory)
    observed: list[tuple[tuple[UUID, ...], int]] = []

    async def observe_publish(
        _redis_client: object,
        *,
        recipient_ids: tuple[UUID, ...],
    ) -> None:
        with notification_stream_factory() as independent_session:
            count = independent_session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.recipient_user_id.in_(recipient_ids))
            )
        observed.append((recipient_ids, count or 0))

    fake_redis = FakeRedis(FakeBroker())
    dependency = importlib.import_module(
        "verboflex.services.notifications"
    ).get_notification_redis_client

    async def fake_dependency() -> AsyncIterator[FakeRedis]:
        try:
            yield fake_redis
        finally:
            await fake_redis.aclose()

    app.dependency_overrides[dependency] = fake_dependency
    monkeypatch.setattr(comment_routes, "publish_notification_invalidations", observe_publish)

    created = asyncio.run(
        _post_comment(
            ids["group"],
            token=token,
            payload=_mention_payload(recipient_id),
        )
    )
    assert created.status_code == 201
    assert observed == [((recipient_id,), 1)]
    assert fake_redis.closed is True

    observed.clear()
    rejected_payload = _mention_payload(uuid4())
    rejected = asyncio.run(_post_comment(ids["group"], token=token, payload=rejected_payload))
    assert rejected.status_code == 422
    assert observed == []


def test_redis_publication_failure_keeps_committed_notification(
    notification_stream_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids, token, _actor_id, recipient_id = _comment_authority(notification_stream_factory)

    async def fail_publish(
        _redis_client: object,
        *,
        recipient_ids: tuple[UUID, ...],
    ) -> None:
        assert recipient_ids == (recipient_id,)
        raise RedisConnectionError("redis endpoint includes private infrastructure")

    fake_redis = FakeRedis(FakeBroker())
    dependency = importlib.import_module(
        "verboflex.services.notifications"
    ).get_notification_redis_client

    async def fake_dependency() -> AsyncIterator[FakeRedis]:
        try:
            yield fake_redis
        finally:
            await fake_redis.aclose()

    app.dependency_overrides[dependency] = fake_dependency
    monkeypatch.setattr(comment_routes, "publish_notification_invalidations", fail_publish)
    response = asyncio.run(
        _post_comment(
            ids["group"],
            token=token,
            payload=_mention_payload(recipient_id),
        )
    )
    assert response.status_code == 201
    with notification_stream_factory() as session:
        rows = tuple(
            session.scalars(
                select(Notification).where(Notification.recipient_user_id == recipient_id)
            )
        )
    assert len(rows) == 1
    assert fake_redis.closed is True
