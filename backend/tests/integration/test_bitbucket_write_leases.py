"""Frozen write authority never renews or reuses a cached connection generation."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.test_bitbucket_oauth import (
    ACCESS_TOKEN,
    ADMIN_ID,
    CLIENT_CREDENTIALS_NOW,
    FakeTokenExchange,
    MutableClock,
    _connection_snapshot,
    oauth_settings,
)
from tests.integration.test_bitbucket_oauth import (
    oauth_migration_database as oauth_migration_database,
)
from tests.integration.test_bitbucket_oauth import (
    oauth_session_factory as oauth_session_factory,
)
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.services.bitbucket_oauth import (
    BitbucketOAuthService,
    OAuthConnectionUnavailable,
    OAuthGenerationRejected,
)


@pytest.fixture
def connected_write_service(
    oauth_session_factory: sessionmaker[Session],
) -> tuple[BitbucketOAuthService, MutableClock, FakeTokenExchange]:
    clock = MutableClock(CLIENT_CREDENTIALS_NOW)
    exchange = FakeTokenExchange()
    service = BitbucketOAuthService(settings=oauth_settings(), token_exchange=exchange, clock=clock)
    with oauth_session_factory() as session:
        assert service.acquire_client_credentials(session).generation == 1
    return service, clock, exchange


@pytest.mark.parametrize("elapsed_seconds", [0, 3540, 3599])
def test_write_lease_preserves_generation_even_within_read_renewal_skew(
    oauth_session_factory: sessionmaker[Session],
    connected_write_service: tuple[BitbucketOAuthService, MutableClock, FakeTokenExchange],
    elapsed_seconds: int,
) -> None:
    service, clock, exchange = connected_write_service
    clock.current += timedelta(seconds=elapsed_seconds)
    before = _connection_snapshot(oauth_session_factory)
    with oauth_session_factory() as session:
        lease = service.acquire_repository_write_lease(session, expected_generation=1)
        assert not session.in_transaction()
        assert lease.generation == 1
        assert lease.access_token == ACCESS_TOKEN
        assert ACCESS_TOKEN not in repr(lease)
        service.require_current_repository_read_lease(session, lease)
        assert not session.in_transaction()
    assert len(exchange.client_credentials_calls) == 1
    assert _connection_snapshot(oauth_session_factory) == before


@pytest.mark.parametrize("expected_generation", [True, False, 0, -1, 1.0, "1", None, 2])
def test_write_lease_rejects_invalid_or_different_expected_generation(
    oauth_session_factory: sessionmaker[Session],
    connected_write_service: tuple[BitbucketOAuthService, MutableClock, FakeTokenExchange],
    expected_generation: object,
) -> None:
    service, _clock, exchange = connected_write_service
    before = _connection_snapshot(oauth_session_factory)
    with oauth_session_factory() as session:
        with pytest.raises(
            OAuthGenerationRejected, match="^Bitbucket connection generation rejected$"
        ):
            service.acquire_repository_write_lease(
                session,
                expected_generation=expected_generation,  # type: ignore[arg-type]
            )
        assert not session.in_transaction()
    assert len(exchange.client_credentials_calls) == 1
    assert _connection_snapshot(oauth_session_factory) == before


@pytest.mark.parametrize("elapsed_seconds", [3600, 3601])
def test_expired_write_lease_never_exchanges_or_changes_stored_authority(
    oauth_session_factory: sessionmaker[Session],
    connected_write_service: tuple[BitbucketOAuthService, MutableClock, FakeTokenExchange],
    elapsed_seconds: int,
) -> None:
    service, clock, exchange = connected_write_service
    clock.current += timedelta(seconds=elapsed_seconds)
    before = _connection_snapshot(oauth_session_factory)
    with oauth_session_factory() as session:
        with pytest.raises(OAuthConnectionUnavailable, match="^Bitbucket connection unavailable$"):
            service.acquire_repository_write_lease(session, expected_generation=1)
        assert not session.in_transaction()
    assert len(exchange.client_credentials_calls) == 1
    assert _connection_snapshot(oauth_session_factory) == before


@pytest.mark.parametrize("transition", ["rotate", "revoke"])
@pytest.mark.parametrize("check", ["acquire", "postcheck"])
def test_write_lease_observes_external_transition_despite_cached_orm_identity(
    oauth_session_factory: sessionmaker[Session],
    connected_write_service: tuple[BitbucketOAuthService, MutableClock, FakeTokenExchange],
    transition: str,
    check: str,
) -> None:
    service, _clock, exchange = connected_write_service
    with oauth_session_factory() as session:
        with session.begin():
            retained_connection = session.get(BitbucketConnection, 1)
        assert retained_connection is not None
        lease = service.acquire_repository_write_lease(session, expected_generation=1)
        with oauth_session_factory() as another_session:
            if transition == "rotate":
                service.acquire_client_credentials(another_session)
            else:
                service.revoke_current(another_session, actor_id=ADMIN_ID)
        assert retained_connection.generation == 1
        expected_error = (
            OAuthGenerationRejected if transition == "rotate" else OAuthConnectionUnavailable
        )
        with pytest.raises(expected_error):
            if check == "acquire":
                service.acquire_repository_write_lease(session, expected_generation=1)
            else:
                service.require_current_repository_read_lease(session, lease)
        assert not session.in_transaction()
    assert len(exchange.client_credentials_calls) == (2 if transition == "rotate" else 1)


def test_write_lease_rejects_ciphertext_damage_with_sanitized_error(
    oauth_session_factory: sessionmaker[Session],
    connected_write_service: tuple[BitbucketOAuthService, MutableClock, FakeTokenExchange],
) -> None:
    service, _clock, exchange = connected_write_service
    with oauth_session_factory() as session, session.begin():
        connection = session.get(BitbucketConnection, 1)
        assert connection is not None
        connection.access_token_ciphertext = "corrupted-ciphertext-must-not-leak"
    with oauth_session_factory() as session:
        with pytest.raises(OAuthConnectionUnavailable, match="^Bitbucket connection unavailable$"):
            service.acquire_repository_write_lease(session, expected_generation=1)
        assert not session.in_transaction()
    assert len(exchange.client_credentials_calls) == 1
