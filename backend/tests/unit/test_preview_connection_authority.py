"""Preview authority uses the same bounded credential policy as Connect/import."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from verboflex.services import preview_jobs
from verboflex.services.bitbucket_oauth import PULLREQUEST_WRITE_SCOPE
from verboflex.services.preview_jobs import (
    PreviewConnectionUnavailable,
    _connected_generation,
    _current_connection,
)


def connection(**overrides):
    return SimpleNamespace(
        **{
            "generation": 7,
            "access_token_ciphertext": "encrypted-test-token",
            "refresh_token_ciphertext": None,
            "scope_profile": PULLREQUEST_WRITE_SCOPE,
            "provider_expires_at": datetime.now(UTC) + timedelta(hours=1),
            "revoked_at": None,
            **overrides,
        }
    )


def session_for(value):
    session = Mock()
    session.execute.return_value.scalar_one_or_none.return_value = value
    return session


@pytest.fixture(autouse=True)
def bitbucket_mapping(monkeypatch):
    # These cases isolate Bitbucket credentials; public GitHub authority is tested separately.
    monkeypatch.setattr(preview_jobs, "_current_mapping", Mock(return_value=None))


@pytest.mark.parametrize("for_update", [False, True])
def test_current_connect_profile_can_create_and_confirm_preview(for_update):
    current = connection()
    session = session_for(current)
    assert _connected_generation(session) == 7
    assert (
        _current_connection(
            session, SimpleNamespace(connection_generation=7), for_update=for_update
        )
        is current
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"scope_profile": "repository"},
        {"scope_profile": "repository:write"},
        {"scope_profile": None},
        {"access_token_ciphertext": None},
        {"refresh_token_ciphertext": "legacy-refresh"},
        {"provider_expires_at": None},
        {"provider_expires_at": datetime.now(UTC) - timedelta(seconds=1)},
        {"revoked_at": datetime.now(UTC)},
    ],
)
def test_preview_rejects_invalid_credential_authority(overrides):
    session = session_for(connection(**overrides))
    with pytest.raises(PreviewConnectionUnavailable):
        _connected_generation(session)
    assert (
        _current_connection(session, SimpleNamespace(connection_generation=7), for_update=True)
        is None
    )


def test_preview_rejects_missing_and_stale_connection():
    with pytest.raises(PreviewConnectionUnavailable):
        _connected_generation(session_for(None))
    assert (
        _current_connection(
            session_for(None), SimpleNamespace(connection_generation=7), for_update=True
        )
        is None
    )
    assert (
        _current_connection(
            session_for(connection()), SimpleNamespace(connection_generation=6), for_update=True
        )
        is None
    )
