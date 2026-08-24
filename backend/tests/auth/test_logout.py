"""HTTP contracts for idempotent session logout."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from tests.auth.test_refresh import (
    REFRESH_TOKEN,
    SESSION_ID,
    FakeRedis,
    configure_dependencies,
    create_refresh_authority,
    refresh_session_factory,
    refresh_settings,
)
from verboflex.auth.access_tokens import issue_access_token
from verboflex.models.auth_session import AuthSession

__all__ = ["refresh_session_factory"]


async def post_logout(
    token: str | None = REFRESH_TOKEN,
    *,
    origin: str | None = "https://app.verboflex.example",
) -> httpx.Response:
    """Call logout through its ambient refresh-cookie boundary."""
    headers = {"Origin": origin} if origin is not None else {}
    cookies = {"verboflex_refresh": token} if token is not None else None
    from verboflex.main import app

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1",
        cookies=cookies,
    ) as client:
        return await client.post("/api/v1/auth/logout", headers=headers)


async def get_me(access_token: str) -> httpx.Response:
    """Use ordinary authority after logout through a protected endpoint."""
    from verboflex.main import app

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1",
    ) as client:
        return await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )


def test_valid_logout_revokes_current_session_and_clears_cookie(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Reach the idempotent target state and invalidate sid-bearing access."""
    authority = create_refresh_authority(refresh_session_factory)
    access_token = issue_access_token(
        user_id=authority.user_id,
        session_id=authority.id,
        token_version=0,
        purpose="access",
        settings=refresh_settings(),
    )
    configure_dependencies(refresh_session_factory, FakeRedis(result=[1, 60]))

    response = asyncio.run(post_logout())

    assert response.status_code == 204
    assert response.content == b""
    set_cookie = response.headers["set-cookie"]
    assert "verboflex_refresh=" in set_cookie
    assert "Max-Age=0" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    with refresh_session_factory() as session:
        persisted = session.get_one(AuthSession, SESSION_ID)
    assert persisted.revoked_at is not None

    protected_response = asyncio.run(get_me(access_token))
    assert protected_response.status_code == 401
    assert protected_response.json() == {"detail": "Invalid access token"}


def assert_cookie_is_cleared(response: httpx.Response) -> None:
    """Assert the one approved deletion path and security attributes."""
    set_cookie = response.headers["set-cookie"]
    assert "verboflex_refresh=" in set_cookie
    assert "Max-Age=0" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_repeated_logout_is_idempotent_and_clears_the_same_cookie_twice(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Return the same non-enumerating target state after authority is revoked."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory, FakeRedis(result=[1, 60]))

    first = asyncio.run(post_logout())
    second = asyncio.run(post_logout())

    assert first.status_code == second.status_code == 204
    assert first.content == second.content == b""
    assert_cookie_is_cleared(first)
    assert_cookie_is_cleared(second)
    with refresh_session_factory() as session:
        persisted = session.get_one(AuthSession, SESSION_ID)
    assert persisted.revoked_at is not None


@pytest.mark.parametrize("token", [None, "", "not-a-refresh-token", "Z" * 42, "Z" * 44])
def test_missing_or_malformed_logout_is_non_enumerating_and_clears_cookie(
    refresh_session_factory: sessionmaker[Session], token: str | None
) -> None:
    """Make invalid ambient authority indistinguishable from the target state."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory, FakeRedis(result=[1, 60]))

    response = asyncio.run(post_logout(token))

    assert response.status_code == 204
    assert response.content == b""
    assert_cookie_is_cleared(response)
    with refresh_session_factory() as session:
        persisted = session.get_one(AuthSession, SESSION_ID)
    assert persisted.revoked_at is None


def test_hostile_origin_cannot_revoke_or_reach_the_logout_limiter(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Reject CSRF before both Redis and PostgreSQL state transitions."""
    create_refresh_authority(refresh_session_factory)
    redis_client = configure_dependencies(refresh_session_factory, FakeRedis(result=[1, 60]))

    response = asyncio.run(post_logout(origin="https://attacker.example"))

    assert response.status_code == 403
    assert response.json() == {"detail": "Origin not allowed"}
    assert "set-cookie" not in response.headers
    assert redis_client.calls == []
    with refresh_session_factory() as session:
        persisted = session.get_one(AuthSession, SESSION_ID)
    assert persisted.revoked_at is None


def test_logout_request_eleven_is_limited_before_revocation(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Return exact 429 metadata without changing the current session."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory, FakeRedis(result=[11, 23]))

    response = asyncio.run(post_logout())

    assert response.status_code == 429
    assert response.json() == {"detail": "Rate limit exceeded"}
    assert response.headers["retry-after"] == "23"
    assert response.headers["x-ratelimit-remaining"] == "0"
    assert "set-cookie" not in response.headers
    with refresh_session_factory() as session:
        persisted = session.get_one(AuthSession, SESSION_ID)
    assert persisted.revoked_at is None
