"""Real PostgreSQL concurrency contracts for refresh rotation."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tests.auth.test_refresh import (
    FAMILY_ID,
    FakeRedis,
    configure_dependencies,
    create_refresh_authority,
    post_refresh,
    refresh_session_factory,
)
from verboflex.models.auth_session import AuthSession

__all__ = ["refresh_session_factory"]


def _submit_refresh() -> tuple[int, dict[str, object]]:
    response = asyncio.run(post_refresh())
    return response.status_code, response.json()


def test_two_real_postgresql_refreshes_create_at_most_one_successor_and_revoke_replay(
    refresh_session_factory: sessionmaker[Session],
) -> None:
    """Serialize predecessor consumption and revoke the family seen by the loser."""
    create_refresh_authority(refresh_session_factory)
    configure_dependencies(refresh_session_factory, FakeRedis(result=[1, 60]))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: _submit_refresh(), range(2)))

    assert sorted(status_code for status_code, _body in results) == [200, 401]
    denied = next(body for status_code, body in results if status_code == 401)
    assert denied == {"detail": "Invalid refresh session"}
    with refresh_session_factory() as session:
        family = session.execute(
            select(AuthSession).where(AuthSession.family_id == FAMILY_ID)
        ).scalars().all()
    successors = [item for item in family if item.parent_id is not None]
    assert len(successors) == 1
    assert len(family) == 2
    assert all(item.revoked_at is not None for item in family)
