"""HTTP contracts for atomic password replacement and global revocation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

import httpx
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.dml import Update

from tests.auth.test_logout import get_me
from tests.auth.test_refresh import (
    FAMILY_ID,
    SESSION_ID,
    USER_ID,
    FakeRedis,
    configure_dependencies,
    refresh_session_factory,
    refresh_settings,
)
from verboflex.auth import password_change as password_change_service
from verboflex.auth.access_tokens import issue_access_token
from verboflex.auth.passwords import hash_password, verify_password
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.user import User

__all__ = ["refresh_session_factory"]

CURRENT_PASSWORD = "temporary password phrase!"
NEW_PASSWORD = "New secure phrase 2026!"
SECOND_SESSION_ID = UUID("00000000-0000-4000-8000-000000000704")


def create_password_change_authority(
    factory: sessionmaker[Session],
    *,
    must_change_password: bool = True,
) -> tuple[str, str]:
    """Persist a forced-change user, two sessions, and old bearer authorities."""
    with factory.begin() as session:
        session.add(
            User(
                id=USER_ID,
                email="person@example.com",
                display_name="Person Example",
                hashed_password=hash_password(CURRENT_PASSWORD),
                must_change_password=must_change_password,
            )
        )
        session.add_all(
            [
                AuthSession(
                    id=SESSION_ID,
                    user_id=USER_ID,
                    family_id=FAMILY_ID,
                    token_hash="a" * 64,
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                ),
                AuthSession(
                    id=SECOND_SESSION_ID,
                    user_id=USER_ID,
                    family_id=SECOND_SESSION_ID,
                    token_hash="b" * 64,
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                ),
            ]
        )
    settings = refresh_settings()
    restricted = issue_access_token(
        user_id=USER_ID,
        token_version=0,
        purpose="password_change",
        settings=settings,
    )
    ordinary = issue_access_token(
        user_id=USER_ID,
        session_id=SESSION_ID,
        token_version=0,
        purpose="access",
        settings=settings,
    )
    return restricted, ordinary


async def post_change_password(
    access_token: str | None,
    *,
    current_password: str = CURRENT_PASSWORD,
    new_password: str = NEW_PASSWORD,
) -> httpx.Response:
    """Submit only credential fields and bearer authority to the registered route."""
    headers = {"Authorization": f"Bearer {access_token}"} if access_token is not None else {}
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1",
    ) as client:
        return await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": current_password,
                "new_password": new_password,
            },
        )


def test_password_change_updates_credentials_and_revokes_all_old_authority(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Commit password, policy, token version, and global revocation atomically."""
    restricted, ordinary = create_password_change_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory, FakeRedis(result=[1, 60]))

    response = asyncio.run(post_change_password(restricted))

    assert response.status_code == 204
    assert response.content == b""
    set_cookie = response.headers["set-cookie"]
    assert "verboflex_refresh=" in set_cookie
    assert "Max-Age=0" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    with refresh_session_factory() as session:
        user = session.get_one(User, USER_ID)
        sessions = (
            session.execute(select(AuthSession).where(AuthSession.user_id == USER_ID))
            .scalars()
            .all()
        )
    assert verify_password(NEW_PASSWORD, user.hashed_password)
    assert not verify_password(CURRENT_PASSWORD, user.hashed_password)
    assert user.must_change_password is False
    assert user.token_version == 1
    assert len(sessions) == 2
    assert all(item.revoked_at is not None for item in sessions)

    old_ordinary_response = asyncio.run(get_me(ordinary))
    assert old_ordinary_response.status_code == 401
    assert old_ordinary_response.json() == {"detail": "Invalid access token"}
    old_restricted_response = asyncio.run(post_change_password(restricted))
    assert old_restricted_response.status_code == 401
    assert old_restricted_response.json() == {"detail": "Invalid access token"}


def durable_password_state(factory: sessionmaker[Session]) -> tuple[str, bool, int, list[object]]:
    """Return credential and session state for rejection atomicity assertions."""
    with factory() as session:
        user = session.get_one(User, USER_ID)
        sessions = (
            session.execute(
                select(AuthSession).where(AuthSession.user_id == USER_ID).order_by(AuthSession.id)
            )
            .scalars()
            .all()
        )
    return (
        user.hashed_password,
        user.must_change_password,
        user.token_version,
        [item.revoked_at for item in sessions],
    )


def test_wrong_current_password_is_exact_400_and_atomic(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Reject wrong current credentials without changing any durable authority."""
    restricted, _ordinary = create_password_change_authority(refresh_session_factory)
    before = durable_password_state(refresh_session_factory)
    configure_dependencies(refresh_session_factory, FakeRedis(result=[1, 60]))

    response = asyncio.run(
        post_change_password(restricted, current_password="wrong current phrase!")
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Current password is incorrect"}
    assert "set-cookie" not in response.headers
    assert durable_password_state(refresh_session_factory) == before


@pytest.mark.parametrize(
    ("new_password", "expected_detail"),
    [
        ("a" * 11, "Password must contain 12 to 128 characters"),
        ("a" * 129, "Password must contain 12 to 128 characters"),
        (CURRENT_PASSWORD, "New password must differ from current password"),
        ("person@example.com", "Password must not equal login email"),
    ],
)
def test_rejected_new_password_policy_is_exact_422_and_atomic(
    refresh_session_factory: sessionmaker[Session],
    new_password: str,
    expected_detail: str,
) -> None:
    """Enforce only the approved boundary, identity, and difference rules."""
    restricted, _ordinary = create_password_change_authority(refresh_session_factory)
    before = durable_password_state(refresh_session_factory)
    configure_dependencies(refresh_session_factory, FakeRedis(result=[1, 60]))

    response = asyncio.run(post_change_password(restricted, new_password=new_password))

    assert response.status_code == 422
    assert response.json() == {"detail": expected_detail}
    assert "set-cookie" not in response.headers
    assert durable_password_state(refresh_session_factory) == before


def test_unicode_and_spaces_are_preserved_in_an_approved_password(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Count Python characters without trimming or inventing composition rules."""
    restricted, _ordinary = create_password_change_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory, FakeRedis(result=[1, 60]))
    unicode_password = "  Frase sicura 🔐  "

    response = asyncio.run(post_change_password(restricted, new_password=unicode_password))

    assert response.status_code == 204
    with refresh_session_factory() as session:
        user = session.get_one(User, USER_ID)
    assert verify_password(unicode_password, user.hashed_password)
    assert not verify_password(unicode_password.strip(), user.hashed_password)


def test_ordinary_current_user_authority_can_change_its_password(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Allow an ordinary principal while keeping restricted purpose local to this route."""
    _restricted, ordinary = create_password_change_authority(
        refresh_session_factory,
        must_change_password=False,
    )
    configure_dependencies(refresh_session_factory, FakeRedis(result=[1, 60]))

    response = asyncio.run(post_change_password(ordinary))

    assert response.status_code == 204
    with refresh_session_factory() as session:
        user = session.get_one(User, USER_ID)
    assert verify_password(NEW_PASSWORD, user.hashed_password)
    assert user.token_version == 1


@pytest.mark.parametrize("access_token", [None, "not-a-signed-token"])
def test_missing_or_malformed_bearer_is_exact_401_without_redis_or_mutation(
    refresh_session_factory: sessionmaker[Session], access_token: str | None
) -> None:
    """Reject unverified subjects before constructing a user-scoped limiter key."""
    create_password_change_authority(refresh_session_factory)
    before = durable_password_state(refresh_session_factory)
    redis_client = configure_dependencies(
        refresh_session_factory,
        FakeRedis(result=[1, 60]),
    )

    response = asyncio.run(post_change_password(access_token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid access token"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert redis_client.calls == []
    assert durable_password_state(refresh_session_factory) == before


def test_password_change_request_eleven_is_limited_before_verification(
    refresh_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return exact 429 metadata without Argon2 or durable mutation."""
    restricted, _ordinary = create_password_change_authority(refresh_session_factory)
    before = durable_password_state(refresh_session_factory)

    def forbidden_verification(_password: str, _password_hash: str) -> bool:
        raise AssertionError("blocked password change must not verify Argon2")

    monkeypatch.setattr(password_change_service, "verify_password", forbidden_verification)
    configure_dependencies(refresh_session_factory, FakeRedis(result=[11, 29]))

    response = asyncio.run(post_change_password(restricted))

    assert response.status_code == 429
    assert response.json() == {"detail": "Rate limit exceeded"}
    assert response.headers["retry-after"] == "29"
    assert response.headers["x-ratelimit-remaining"] == "0"
    assert durable_password_state(refresh_session_factory) == before


def test_redis_outage_fails_closed_before_password_verification(
    refresh_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return exact 503 without Argon2 or durable mutation when limiting is unavailable."""
    restricted, _ordinary = create_password_change_authority(refresh_session_factory)
    before = durable_password_state(refresh_session_factory)

    def forbidden_verification(_password: str, _password_hash: str) -> bool:
        raise AssertionError("Redis outage must not verify Argon2")

    monkeypatch.setattr(password_change_service, "verify_password", forbidden_verification)
    configure_dependencies(
        refresh_session_factory,
        FakeRedis(result=RedisConnectionError("redis unavailable")),
    )

    response = asyncio.run(post_change_password(restricted))

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service unavailable"}
    assert durable_password_state(refresh_session_factory) == before


def test_database_failure_rolls_back_credential_and_authority_changes(
    refresh_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Roll back user fields when global session revocation cannot be persisted."""
    restricted, _ordinary = create_password_change_authority(refresh_session_factory)
    before = durable_password_state(refresh_session_factory)
    configure_dependencies(refresh_session_factory, FakeRedis(result=[1, 60]))
    original_execute = cast(Any, Session.execute)

    def fail_session_update(session: Session, statement: object, *args: Any, **kwargs: Any) -> Any:
        if isinstance(statement, Update):
            raise RuntimeError("injected session update failure")
        return original_execute(session, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", fail_session_update)

    response = asyncio.run(post_change_password(restricted))

    assert response.status_code == 500
    monkeypatch.setattr(Session, "execute", original_execute)
    assert durable_password_state(refresh_session_factory) == before
