"""HTTP contracts for atomic password replacement and global revocation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

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
) -> tuple[str, str]:
    """Persist a forced-change user, two sessions, and old bearer authorities."""
    with factory.begin() as session:
        session.add(
            User(
                id=USER_ID,
                email="person@example.com",
                display_name="Person Example",
                hashed_password=hash_password(CURRENT_PASSWORD),
                must_change_password=True,
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
    headers = (
        {"Authorization": f"Bearer {access_token}"} if access_token is not None else {}
    )
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
        sessions = session.execute(
            select(AuthSession).where(AuthSession.user_id == USER_ID)
        ).scalars().all()
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
