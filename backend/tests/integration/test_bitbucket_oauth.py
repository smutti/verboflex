"""Provider-mocked contracts for the organizational Bitbucket OAuth authority."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from pydantic import AnyHttpUrl, SecretStr
from sqlalchemy import Engine, create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.core.config import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)
ADMIN_ID = UUID("00000000-0000-4000-8000-000000000901")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000902")
CALLBACK_URI = "https://api.verboflex.example/api/v1/admin/bitbucket/callback"
FIXED_POST_CALLBACK_PATH = "/admin/bitbucket"
FERNET_KEY = base64.urlsafe_b64encode(b"0" * 32).decode()
WRONG_FERNET_KEY = base64.urlsafe_b64encode(b"1" * 32).decode()
ACCESS_TOKEN = "provider-access-token-must-never-leak"
REFRESH_TOKEN = "provider-refresh-token-must-never-leak"
PROVIDER_ERROR_BODY = "provider-body-must-never-leak"


@dataclass
class FakeRedis:
    """String-only Redis seam with observable exact TTL and atomic GETDEL."""

    values: dict[str, str] = field(default_factory=dict)
    set_calls: list[tuple[str, str, int, bool]] = field(default_factory=list)
    getdel_calls: list[str] = field(default_factory=list)

    def set(
        self,
        name: str,
        value: str,
        *,
        ex: int,
        nx: bool,
    ) -> bool:
        """Store one value only when the digest key is unused."""
        self.set_calls.append((name, value, ex, nx))
        if nx and name in self.values:
            return False
        self.values[name] = value
        return True

    def getdel(self, name: str) -> str | None:
        """Return and delete one state binding atomically."""
        self.getdel_calls.append(name)
        return self.values.pop(name, None)

    def expire_all(self) -> None:
        """Model Redis expiry without granting a non-atomic read seam."""
        self.values.clear()


@dataclass
class FakeTokenExchange:
    """Backend-only provider boundary with observable sanitized calls."""

    calls: list[dict[str, str]] = field(default_factory=list)
    scope: str = "repository"
    error: Exception | None = None

    def exchange_authorization_code(
        self,
        *,
        code: str,
        callback_uri: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any]:
        """Return one exact provider response or an opaque provider failure."""
        self.calls.append(
            {
                "code": code,
                "callback_uri": callback_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            }
        )
        if self.error is not None:
            raise self.error
        return {
            "access_token": ACCESS_TOKEN,
            "refresh_token": REFRESH_TOKEN,
            "scope": self.scope,
            "expires_in": 3600,
            "provider_debug_body": PROVIDER_ERROR_BODY,
        }


@pytest.fixture
def oauth_migration_database() -> Iterator[tuple[Config, Engine]]:
    """Migrate one isolated PostgreSQL database for OAuth persistence."""
    database_name = f"verboflex_oauth_{uuid4().hex}"
    with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
        admin_connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )

    database_url = ADMIN_DATABASE_URL.rsplit("/", 1)[0] + f"/{database_name}"
    sqlalchemy_url = database_url.replace("postgresql://", "postgresql+psycopg://")
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlalchemy_url)
    engine = create_engine(sqlalchemy_url)
    command.upgrade(config, "head")
    try:
        yield config, engine
    finally:
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


@pytest.fixture
def oauth_session_factory(
    oauth_migration_database: tuple[Config, Engine],
) -> Iterator[sessionmaker[Session]]:
    """Expose sessions over the migrated OAuth database."""
    _config, engine = oauth_migration_database
    yield sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def oauth_settings() -> Settings:
    """Return an explicit complete OAuth configuration with no client exposure."""
    return Settings(
        bitbucket_oauth_client_id="verboflex-test-client",
        bitbucket_oauth_client_secret=SecretStr("backend-only-client-secret"),
        bitbucket_oauth_callback_uri=AnyHttpUrl(CALLBACK_URI),
        bitbucket_oauth_post_callback_path=FIXED_POST_CALLBACK_PATH,
        bitbucket_token_encryption_keyring=SecretStr(FERNET_KEY),
    )


def _connection_snapshot(factory: sessionmaker[Session]) -> tuple[Any, ...]:
    from verboflex.models.bitbucket_connection import BitbucketConnection

    with factory() as session:
        connection = session.execute(select(BitbucketConnection)).scalar_one()
        return (
            connection.generation,
            connection.access_token_ciphertext,
            connection.refresh_token_ciphertext,
            connection.scope_profile,
            connection.provider_expires_at,
            connection.connected_at,
            connection.revoked_at,
        )


def test_connects_single_encrypted_repository_scope_generation(
    oauth_session_factory: sessionmaker[Session],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Connect once and reject every replay, binding, scope, and redirect attack."""
    from verboflex.models.bitbucket_connection import BitbucketConnection
    from verboflex.services.bitbucket_oauth import (
        BitbucketOAuthService,
        OAuthCallbackRejected,
    )

    redis = FakeRedis()
    exchange = FakeTokenExchange()
    entropy_calls: list[int] = []
    entropy_counter = 0

    def random_bytes(length: int) -> bytes:
        nonlocal entropy_counter
        entropy_calls.append(length)
        entropy_counter += 1
        return entropy_counter.to_bytes(length, byteorder="big")

    service = BitbucketOAuthService(
        settings=oauth_settings(),
        redis_client=redis,
        token_exchange=exchange,
        random_bytes=random_bytes,
    )

    state = service.start(
        admin_id=ADMIN_ID,
        session_id=SESSION_ID,
        expected_generation=0,
    )

    assert entropy_calls == [32]
    assert isinstance(state, str)
    assert len(state) == 43
    state_digest = hashlib.sha256(state.encode()).hexdigest()
    assert redis.set_calls == [
        (
            f"verboflex:bitbucket:oauth-state:{state_digest}",
            redis.set_calls[0][1],
            600,
            True,
        )
    ]
    stored_binding = json.loads(redis.set_calls[0][1])
    assert stored_binding == {
        "admin_id": str(ADMIN_ID),
        "callback_uri": CALLBACK_URI,
        "expected_generation": 0,
        "post_callback_path": FIXED_POST_CALLBACK_PATH,
        "session_id": str(SESSION_ID),
    }
    assert state not in redis.set_calls[0][0]
    assert state not in redis.set_calls[0][1]

    with oauth_session_factory() as session:
        result = service.complete_callback(
            session,
            state=state,
            code="single-use-authorization-code",
            admin_id=ADMIN_ID,
            session_id=SESSION_ID,
            callback_uri=CALLBACK_URI,
            post_callback_path=FIXED_POST_CALLBACK_PATH,
        )

    assert redis.getdel_calls == [f"verboflex:bitbucket:oauth-state:{state_digest}"]
    assert exchange.calls == [
        {
            "code": "single-use-authorization-code",
            "callback_uri": CALLBACK_URI,
            "client_id": "verboflex-test-client",
            "client_secret": "backend-only-client-secret",
        }
    ]
    assert result.redirect_path == FIXED_POST_CALLBACK_PATH
    assert result.status.state == "connected"
    assert result.status.generation == 1
    assert result.status.scope_profile == "repository"
    assert set(result.status.__dataclass_fields__) == {
        "state",
        "generation",
        "scope_profile",
    }

    with oauth_session_factory() as session:
        connection = session.execute(select(BitbucketConnection)).scalar_one()
        assert connection.id == 1
        assert connection.generation == 1
        assert connection.scope_profile == "repository"
        assert connection.access_token_ciphertext not in (None, ACCESS_TOKEN)
        assert connection.refresh_token_ciphertext not in (None, REFRESH_TOKEN)
        persistence_text = repr(
            {
                column.name: getattr(connection, column.name)
                for column in BitbucketConnection.__table__.columns
            }
        )
        assert ACCESS_TOKEN not in persistence_text
        assert REFRESH_TOKEN not in persistence_text
        assert PROVIDER_ERROR_BODY not in persistence_text

    connected_snapshot = _connection_snapshot(oauth_session_factory)
    provider_call_count = len(exchange.calls)

    def assert_rejected_without_exchange_or_mutation(
        attack_state: str,
        **overrides: object,
    ) -> None:
        arguments: dict[str, object] = {
            "state": attack_state,
            "code": "attacker-code",
            "admin_id": ADMIN_ID,
            "session_id": SESSION_ID,
            "callback_uri": CALLBACK_URI,
            "post_callback_path": FIXED_POST_CALLBACK_PATH,
        }
        arguments.update(overrides)
        with (
            oauth_session_factory() as session,
            pytest.raises(OAuthCallbackRejected, match="OAuth callback rejected"),
        ):
            service.complete_callback(session, **arguments)
        assert len(exchange.calls) == provider_call_count
        assert _connection_snapshot(oauth_session_factory) == connected_snapshot

    assert_rejected_without_exchange_or_mutation(state)

    tamper_state = service.start(
        admin_id=ADMIN_ID,
        session_id=SESSION_ID,
        expected_generation=1,
    )
    assert_rejected_without_exchange_or_mutation(tamper_state[:-1] + "A")

    wrong_admin_state = service.start(
        admin_id=ADMIN_ID,
        session_id=SESSION_ID,
        expected_generation=1,
    )
    assert_rejected_without_exchange_or_mutation(wrong_admin_state, admin_id=uuid4())

    wrong_session_state = service.start(
        admin_id=ADMIN_ID,
        session_id=SESSION_ID,
        expected_generation=1,
    )
    assert_rejected_without_exchange_or_mutation(wrong_session_state, session_id=uuid4())

    callback_mismatch_state = service.start(
        admin_id=ADMIN_ID,
        session_id=SESSION_ID,
        expected_generation=1,
    )
    assert_rejected_without_exchange_or_mutation(
        callback_mismatch_state,
        callback_uri="https://attacker.example/callback",
    )

    open_redirect_state = service.start(
        admin_id=ADMIN_ID,
        session_id=SESSION_ID,
        expected_generation=1,
    )
    assert_rejected_without_exchange_or_mutation(
        open_redirect_state,
        post_callback_path="https://attacker.example/steal",
    )

    expired_state = service.start(
        admin_id=ADMIN_ID,
        session_id=SESSION_ID,
        expected_generation=1,
    )
    redis.expire_all()
    assert_rejected_without_exchange_or_mutation(expired_state)

    wrong_generation_state = service.start(
        admin_id=ADMIN_ID,
        session_id=SESSION_ID,
        expected_generation=1,
    )
    with oauth_session_factory.begin() as session:
        connection = session.execute(select(BitbucketConnection).with_for_update()).scalar_one()
        connection.generation = 2
    generation_snapshot = _connection_snapshot(oauth_session_factory)
    with (
        oauth_session_factory() as session,
        pytest.raises(OAuthCallbackRejected, match="OAuth callback rejected"),
    ):
        service.complete_callback(
            session,
            state=wrong_generation_state,
            code="stale-generation-code",
            admin_id=ADMIN_ID,
            session_id=SESSION_ID,
            callback_uri=CALLBACK_URI,
            post_callback_path=FIXED_POST_CALLBACK_PATH,
        )
    assert len(exchange.calls) == provider_call_count
    assert _connection_snapshot(oauth_session_factory) == generation_snapshot

    scope_state = service.start(
        admin_id=ADMIN_ID,
        session_id=SESSION_ID,
        expected_generation=2,
    )
    exchange.scope = "repository:write"
    with (
        oauth_session_factory() as session,
        pytest.raises(OAuthCallbackRejected, match="OAuth callback rejected"),
    ):
        service.complete_callback(
            session,
            state=scope_state,
            code="over-scoped-code",
            admin_id=ADMIN_ID,
            session_id=SESSION_ID,
            callback_uri=CALLBACK_URI,
            post_callback_path=FIXED_POST_CALLBACK_PATH,
        )
    assert len(exchange.calls) == provider_call_count + 1
    assert _connection_snapshot(oauth_session_factory) == generation_snapshot

    provider_error_state = service.start(
        admin_id=ADMIN_ID,
        session_id=SESSION_ID,
        expected_generation=2,
    )
    exchange.scope = "repository"
    exchange.error = RuntimeError(PROVIDER_ERROR_BODY)
    with (
        oauth_session_factory() as session,
        pytest.raises(OAuthCallbackRejected, match="OAuth callback rejected") as error,
    ):
        service.complete_callback(
            session,
            state=provider_error_state,
            code="provider-failure-code",
            admin_id=ADMIN_ID,
            session_id=SESSION_ID,
            callback_uri=CALLBACK_URI,
            post_callback_path=FIXED_POST_CALLBACK_PATH,
        )
    assert PROVIDER_ERROR_BODY not in str(error.value)
    assert ACCESS_TOKEN not in caplog.text
    assert REFRESH_TOKEN not in caplog.text
    assert PROVIDER_ERROR_BODY not in caplog.text
    assert _connection_snapshot(oauth_session_factory) == generation_snapshot

    with pytest.raises(ValueError, match="Bitbucket OAuth settings are required"):
        BitbucketOAuthService(
            settings=Settings(),
            redis_client=redis,
            token_exchange=exchange,
            random_bytes=random_bytes,
        )

    invalid_key_settings = oauth_settings().model_copy(
        update={"bitbucket_token_encryption_keyring": SecretStr("not-a-fernet-key")}
    )
    with pytest.raises(ValueError, match="Bitbucket token encryption keyring is invalid"):
        BitbucketOAuthService(
            settings=invalid_key_settings,
            redis_client=redis,
            token_exchange=exchange,
            random_bytes=random_bytes,
        )


def test_secret_box_rejects_wrong_key_tamper_and_plaintext_representations() -> None:
    """Authenticated encryption rejects every invalid ciphertext without disclosure."""
    from verboflex.security.secret_box import SecretBox, SecretBoxDecryptionError

    secret_box = SecretBox.from_keyring(FERNET_KEY)
    ciphertext = secret_box.encrypt(ACCESS_TOKEN)

    assert secret_box.decrypt(ciphertext) == ACCESS_TOKEN
    assert ACCESS_TOKEN not in ciphertext
    assert REFRESH_TOKEN not in ciphertext
    assert FERNET_KEY not in repr(secret_box)
    assert ACCESS_TOKEN not in repr(secret_box)
    assert repr(secret_box) == "SecretBox(<redacted>)"

    wrong_key_box = SecretBox.from_keyring(WRONG_FERNET_KEY)
    with pytest.raises(
        SecretBoxDecryptionError,
        match="Encrypted secret is invalid",
    ) as wrong_key_error:
        wrong_key_box.decrypt(ciphertext)
    assert ACCESS_TOKEN not in str(wrong_key_error.value)
    assert ciphertext not in str(wrong_key_error.value)

    final_character = "A" if ciphertext[-1] != "A" else "B"
    tampered_ciphertext = f"{ciphertext[:-1]}{final_character}"
    with pytest.raises(
        SecretBoxDecryptionError,
        match="Encrypted secret is invalid",
    ) as tamper_error:
        secret_box.decrypt(tampered_ciphertext)
    assert ACCESS_TOKEN not in str(tamper_error.value)
    assert tampered_ciphertext not in str(tamper_error.value)


def test_secret_box_drives_oauth_persistence_without_secret_metadata(
    oauth_session_factory: sessionmaker[Session],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """OAuth persistence uses the narrow box while state and status stay bounded."""
    from verboflex.models.bitbucket_connection import BitbucketConnection
    from verboflex.security.secret_box import SecretBox
    from verboflex.services.bitbucket_oauth import BitbucketOAuthService

    redis = FakeRedis()
    exchange = FakeTokenExchange()
    service = BitbucketOAuthService(
        settings=oauth_settings(),
        redis_client=redis,
        token_exchange=exchange,
        random_bytes=lambda length: b"2" * length,
    )
    state = service.start(
        admin_id=ADMIN_ID,
        session_id=SESSION_ID,
        expected_generation=0,
    )
    with oauth_session_factory() as session:
        result = service.complete_callback(
            session,
            state=state,
            code="audit-safe-authorization-code",
            admin_id=ADMIN_ID,
            session_id=SESSION_ID,
            callback_uri=CALLBACK_URI,
            post_callback_path=FIXED_POST_CALLBACK_PATH,
        )

    secret_box = SecretBox.from_keyring(FERNET_KEY)
    with oauth_session_factory() as session:
        connection = session.execute(select(BitbucketConnection)).scalar_one()
        assert connection.access_token_ciphertext is not None
        assert connection.refresh_token_ciphertext is not None
        assert secret_box.decrypt(connection.access_token_ciphertext) == ACCESS_TOKEN
        assert secret_box.decrypt(connection.refresh_token_ciphertext) == REFRESH_TOKEN

    state_storage = json.dumps(redis.values, sort_keys=True)
    audit_safe_status = repr(result.status)
    for secret in (
        ACCESS_TOKEN,
        REFRESH_TOKEN,
        PROVIDER_ERROR_BODY,
        "backend-only-client-secret",
        "audit-safe-authorization-code",
    ):
        assert secret not in state_storage
        assert secret not in audit_safe_status
        assert secret not in caplog.text


def test_bitbucket_singleton_metadata_survives_postgresql_rehearsal(
    oauth_migration_database: tuple[Config, Engine],
) -> None:
    """Declarative registration and upgrade/downgrade/upgrade remain exact."""
    from verboflex import models
    from verboflex.db.base import Base
    from verboflex.models.bitbucket_connection import BitbucketConnection

    config, engine = oauth_migration_database
    assert models.BitbucketConnection is BitbucketConnection
    assert "BitbucketConnection" in models.__all__
    assert Base.metadata.tables["bitbucket_connections"] is BitbucketConnection.__table__

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("bitbucket_connections")}
    assert columns == {
        "id",
        "generation",
        "access_token_ciphertext",
        "refresh_token_ciphertext",
        "scope_profile",
        "provider_expires_at",
        "connected_at",
        "revoked_at",
        "created_at",
        "updated_at",
    }
    assert "access_token" not in columns
    assert "refresh_token" not in columns
    assert {
        constraint["name"]
        for constraint in inspector.get_check_constraints("bitbucket_connections")
    } == {
        "ck_bitbucket_connections_credential_pair_state",
        "ck_bitbucket_connections_generation_non_negative",
        "ck_bitbucket_connections_singleton_id",
    }
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT count(*) FROM bitbucket_connections").scalar_one()
            == 1
        )

    command.downgrade(config, "0003_repositories")
    assert "bitbucket_connections" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    assert "bitbucket_connections" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT count(*) FROM bitbucket_connections").scalar_one()
            == 1
        )
