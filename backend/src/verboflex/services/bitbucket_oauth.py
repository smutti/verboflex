"""Expiry-safe Bitbucket client-credentials connection authority."""

from __future__ import annotations

import json
from base64 import b64encode
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http.client import HTTPMessage
from typing import IO, Literal, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, OpenerDirector, Request, build_opener
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.audit.events import (
    AuditAction,
    AuditEventEmitter,
    emit_audit_event,
    new_audit_event,
)
from verboflex.core.config import Settings
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.security.secret_box import (
    SecretBox,
    SecretBoxConfigurationError,
    SecretBoxDecryptionError,
)

REPOSITORY_SCOPE = "repository"
SETTINGS_REQUIRED_MESSAGE = "Bitbucket OAuth settings are required"
INVALID_KEYRING_MESSAGE = "Bitbucket token encryption keyring is invalid"
GENERATION_REJECTED_MESSAGE = "Bitbucket connection generation rejected"
CONNECTION_UNAVAILABLE_MESSAGE = "Bitbucket connection unavailable"
BITBUCKET_TOKEN_URL = "https://bitbucket.org/site/oauth2/access_token"
TOKEN_EXCHANGE_TIMEOUT_SECONDS = 10
MAX_TOKEN_RESPONSE_BYTES = 65_536
TOKEN_RENEWAL_SKEW_SECONDS = 60


class TokenExchange(Protocol):
    """Backend-only provider token exchange boundary."""

    def exchange_client_credentials(
        self,
        *,
        client_id: str,
        client_secret: str,
    ) -> Mapping[str, object]:
        """Acquire one access-only organizational credential."""
        ...


class OAuthGenerationRejected(PermissionError):
    """Reject work bound to any non-current provider generation."""


class OAuthConnectionUnavailable(RuntimeError):
    """Bound provider or ciphertext failures without exposing diagnostics."""


class _RejectRedirects(HTTPRedirectHandler):
    """Keep provider credentials on the one exact token endpoint."""

    def redirect_request(
        self,
        request: Request,
        file_pointer: IO[bytes],
        code: int,
        message: str,
        headers: HTTPMessage,
        new_url: str,
    ) -> Request | None:
        return None


class BitbucketOAuthTokenExchange:
    """Bounded standard-library adapter for Bitbucket's exact token endpoint."""

    def __init__(self, *, opener: OpenerDirector | None = None) -> None:
        self._opener = opener or build_opener(_RejectRedirects())

    def exchange_client_credentials(
        self,
        *,
        client_id: str,
        client_secret: str,
    ) -> Mapping[str, object]:
        credentials = b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
        request = Request(
            BITBUCKET_TOKEN_URL,
            data=urlencode({"grant_type": "client_credentials"}).encode("ascii"),
            headers={
                "Accept": "application/json",
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with self._opener.open(
                request,
                timeout=TOKEN_EXCHANGE_TIMEOUT_SECONDS,
            ) as response:
                payload = response.read(MAX_TOKEN_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, OSError, TimeoutError) as error:
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE) from error
        if len(payload) > MAX_TOKEN_RESPONSE_BYTES:
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)
        try:
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE) from error
        if not isinstance(decoded, dict):
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)
        return cast(dict[str, object], decoded)


@dataclass(frozen=True, slots=True)
class BitbucketConnectionStatus:
    """Bounded provider state safe for later API projection."""

    state: str
    generation: int
    scope_profile: str


@dataclass(frozen=True, slots=True)
class BitbucketConnectionPublicStatus:
    """Timestamp-bounded connection projection with no credential generation."""

    state: Literal[
        "disconnected",
        "connected",
        "reauthorization_required",
        "unavailable",
    ]
    connected_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class BitbucketCredentialLease:
    """One transient repository-read credential bound to a durable generation."""

    generation: int
    access_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class BitbucketLocalRevocation:
    """Local credential invalidation plus its bounded public projection."""

    status: BitbucketConnectionStatus
    public_status: BitbucketConnectionPublicStatus


def revoke_local_bitbucket_connection(
    session: Session,
    *,
    actor_id: UUID,
    expected_generation: int | None = None,
    audit_emitter: AuditEventEmitter = emit_audit_event,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> BitbucketLocalRevocation:
    """Clear local authority without requiring usable provider configuration."""
    revoked_at = clock()
    if revoked_at.tzinfo is None or revoked_at.utcoffset() is None:
        raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)
    revoked_at = revoked_at.astimezone(UTC)
    changed = False
    with session.begin():
        connection = session.execute(
            select(BitbucketConnection).where(BitbucketConnection.id == 1).with_for_update()
        ).scalar_one_or_none()
        if connection is None:
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)
        previous_generation = connection.generation
        if (
            connection.revoked_at is not None
            and connection.access_token_ciphertext is None
            and connection.refresh_token_ciphertext is None
        ):
            status = BitbucketConnectionStatus(
                state="revoked",
                generation=connection.generation,
                scope_profile=connection.scope_profile or REPOSITORY_SCOPE,
            )
        else:
            if expected_generation is not None and connection.generation != expected_generation:
                raise OAuthGenerationRejected(GENERATION_REJECTED_MESSAGE)
            connection.generation += 1
            connection.access_token_ciphertext = None
            connection.refresh_token_ciphertext = None
            connection.provider_expires_at = None
            connection.revoked_at = revoked_at
            session.flush()
            changed = True
            status = BitbucketConnectionStatus(
                state="revoked",
                generation=connection.generation,
                scope_profile=connection.scope_profile or REPOSITORY_SCOPE,
            )
        public_status = BitbucketConnectionPublicStatus(
            state="disconnected",
            connected_at=connection.connected_at,
            expires_at=None,
            revoked_at=connection.revoked_at,
        )
    if changed:
        audit_emitter(
            new_audit_event(
                action="bitbucket.revoked",
                actor_id=actor_id,
                from_generation=previous_generation,
                to_generation=status.generation,
                occurred_at=revoked_at,
            )
        )
    return BitbucketLocalRevocation(status=status, public_status=public_status)


class BitbucketOAuthService:
    """Own encrypted access-only credentials and expiry-safe leases."""

    def __init__(
        self,
        *,
        settings: Settings,
        token_exchange: TokenExchange,
        audit_emitter: AuditEventEmitter = emit_audit_event,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._token_exchange = token_exchange
        self._audit_emitter = audit_emitter
        self._clock = clock
        self._client_id, self._client_secret = self._require_oauth_settings(settings)
        self._secret_box = self._build_secret_box(settings)

    @staticmethod
    def _require_oauth_settings(settings: Settings) -> tuple[str, str]:
        client_id = settings.bitbucket_oauth_client_id
        client_secret = settings.bitbucket_oauth_client_secret
        if client_id is None or client_secret is None:
            raise ValueError(SETTINGS_REQUIRED_MESSAGE)
        normalized_client_id = client_id.strip()
        normalized_client_secret = client_secret.get_secret_value()
        if not normalized_client_id or not normalized_client_secret:
            raise ValueError(SETTINGS_REQUIRED_MESSAGE)
        return normalized_client_id, normalized_client_secret

    @staticmethod
    def _build_secret_box(settings: Settings) -> SecretBox:
        keyring = settings.bitbucket_token_encryption_keyring
        if keyring is None:
            raise ValueError(SETTINGS_REQUIRED_MESSAGE)
        try:
            return SecretBox.from_keyring(keyring.get_secret_value())
        except SecretBoxConfigurationError as error:
            raise ValueError(INVALID_KEYRING_MESSAGE) from error

    def public_status(self, session: Session) -> BitbucketConnectionPublicStatus:
        """Read one bounded status with provider expiry as authoritative."""
        with session.begin():
            connection = session.get(BitbucketConnection, 1)
            if connection is None:
                return self._status("unavailable", None)
            has_access = connection.access_token_ciphertext is not None
            has_refresh = connection.refresh_token_ciphertext is not None
            if has_refresh and not has_access:
                state: Literal[
                    "disconnected",
                    "connected",
                    "reauthorization_required",
                    "unavailable",
                ] = "unavailable"
            elif connection.revoked_at is not None:
                state = "disconnected"
            elif has_refresh:
                state = "reauthorization_required"
            elif has_access and connection.scope_profile != REPOSITORY_SCOPE:
                state = "unavailable"
            elif has_access and (
                connection.provider_expires_at is None
                or connection.provider_expires_at <= self._now()
            ):
                state = "reauthorization_required"
            elif has_access:
                state = "connected"
            elif connection.connected_at is not None or connection.provider_expires_at is not None:
                state = "reauthorization_required"
            else:
                state = "disconnected"
            return self._status(state, connection)

    @staticmethod
    def _status(
        state: Literal[
            "disconnected",
            "connected",
            "reauthorization_required",
            "unavailable",
        ],
        connection: BitbucketConnection | None,
    ) -> BitbucketConnectionPublicStatus:
        return BitbucketConnectionPublicStatus(
            state=state,
            connected_at=None if connection is None else connection.connected_at,
            expires_at=None if connection is None else connection.provider_expires_at,
            revoked_at=None if connection is None else connection.revoked_at,
        )

    def acquire_client_credentials(
        self,
        session: Session,
        *,
        actor_id: UUID | None = None,
    ) -> BitbucketConnectionStatus:
        """Acquire and persist one encrypted access-only generation under row lock."""
        connected_at = self._now()
        with session.begin():
            connection = self._lock_connection(session)
            access_token, expires_in = self._exchange_and_validate()
            previous_generation = connection.generation
            status = self._persist_access_only(
                session,
                connection,
                access_token=access_token,
                expires_in=expires_in,
                acquired_at=connected_at,
                replace_connected_at=True,
            )
        if actor_id is not None:
            self._emit_lifecycle_event(
                action="bitbucket.connected",
                actor_id=actor_id,
                from_generation=previous_generation,
                to_generation=status.generation,
                occurred_at=connected_at,
            )
        return status

    def acquire_repository_read_lease(self, session: Session) -> BitbucketCredentialLease:
        """Renew when needed, then decrypt one unexpired current access token."""
        self._renew_access_token_if_needed(session)
        with session.begin():
            connection = session.get(BitbucketConnection, 1)
            self._require_readable_connection(connection)
            assert connection is not None
            assert connection.access_token_ciphertext is not None
            try:
                access_token = self._secret_box.decrypt(connection.access_token_ciphertext)
            except SecretBoxDecryptionError as error:
                raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE) from error
            return BitbucketCredentialLease(
                generation=connection.generation,
                access_token=access_token,
            )

    def require_current_repository_read_lease(
        self,
        session: Session,
        lease: BitbucketCredentialLease,
    ) -> None:
        """Reject provider work whose credential generation is stale or expired."""
        with session.begin():
            connection = session.get(BitbucketConnection, 1)
            self._require_readable_connection(connection)
            assert connection is not None
            if connection.generation != lease.generation:
                raise OAuthGenerationRejected(GENERATION_REJECTED_MESSAGE)

    def _renew_access_token_if_needed(self, session: Session) -> None:
        renewal_error: OAuthConnectionUnavailable | None = None
        renewed_at = self._now()
        with session.begin():
            connection = self._lock_connection(session)
            self._require_client_credentials_state(connection)
            assert connection.provider_expires_at is not None
            if connection.provider_expires_at > renewed_at + timedelta(
                seconds=TOKEN_RENEWAL_SKEW_SECONDS
            ):
                return
            try:
                access_token, expires_in = self._exchange_and_validate()
            except OAuthConnectionUnavailable as error:
                self._invalidate_expired_generation(session, connection)
                renewal_error = error
            else:
                self._persist_access_only(
                    session,
                    connection,
                    access_token=access_token,
                    expires_in=expires_in,
                    acquired_at=renewed_at,
                    replace_connected_at=False,
                )
        if renewal_error is not None:
            raise renewal_error

    def _exchange_and_validate(self) -> tuple[str, int]:
        try:
            token_response = self._token_exchange.exchange_client_credentials(
                client_id=self._client_id,
                client_secret=self._client_secret,
            )
            return self._require_client_credentials_response(token_response)
        except OAuthConnectionUnavailable:
            raise
        except Exception as error:
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE) from error

    def _persist_access_only(
        self,
        session: Session,
        connection: BitbucketConnection,
        *,
        access_token: str,
        expires_in: int,
        acquired_at: datetime,
        replace_connected_at: bool,
    ) -> BitbucketConnectionStatus:
        connection.generation += 1
        connection.access_token_ciphertext = self._secret_box.encrypt(access_token)
        connection.refresh_token_ciphertext = None
        connection.scope_profile = REPOSITORY_SCOPE
        connection.provider_expires_at = acquired_at + timedelta(seconds=expires_in)
        if replace_connected_at or connection.connected_at is None:
            connection.connected_at = acquired_at
        connection.revoked_at = None
        session.flush()
        return BitbucketConnectionStatus(
            state="connected",
            generation=connection.generation,
            scope_profile=REPOSITORY_SCOPE,
        )

    @staticmethod
    def _invalidate_expired_generation(
        session: Session,
        connection: BitbucketConnection,
    ) -> None:
        connection.generation += 1
        connection.access_token_ciphertext = None
        connection.refresh_token_ciphertext = None
        connection.revoked_at = None
        session.flush()

    def revoke(
        self,
        session: Session,
        *,
        expected_generation: int,
        actor_id: UUID,
    ) -> BitbucketConnectionStatus:
        """Immediately invalidate one local generation without provider claims."""
        return self._revoke_local(
            session,
            actor_id=actor_id,
            expected_generation=expected_generation,
        )

    def revoke_current(
        self,
        session: Session,
        *,
        actor_id: UUID,
    ) -> BitbucketConnectionStatus:
        """Invalidate whichever generation is current at lock acquisition."""
        return self._revoke_local(session, actor_id=actor_id, expected_generation=None)

    def _revoke_local(
        self,
        session: Session,
        *,
        actor_id: UUID,
        expected_generation: int | None,
    ) -> BitbucketConnectionStatus:
        return revoke_local_bitbucket_connection(
            session,
            actor_id=actor_id,
            expected_generation=expected_generation,
            audit_emitter=self._audit_emitter,
            clock=self._clock,
        ).status

    def _require_client_credentials_state(self, connection: BitbucketConnection) -> None:
        if (
            connection.revoked_at is not None
            or connection.scope_profile != REPOSITORY_SCOPE
            or connection.access_token_ciphertext is None
            or connection.refresh_token_ciphertext is not None
            or connection.provider_expires_at is None
        ):
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)

    def _require_readable_connection(self, connection: BitbucketConnection | None) -> None:
        if connection is None:
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)
        self._require_client_credentials_state(connection)
        assert connection.provider_expires_at is not None
        if connection.provider_expires_at <= self._now():
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)

    @staticmethod
    def _lock_connection(session: Session) -> BitbucketConnection:
        connection = session.execute(
            select(BitbucketConnection).where(BitbucketConnection.id == 1).with_for_update()
        ).scalar_one_or_none()
        if connection is None:
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)
        return connection

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)
        return value.astimezone(UTC)

    def _emit_lifecycle_event(
        self,
        *,
        action: AuditAction,
        actor_id: UUID,
        from_generation: int,
        to_generation: int,
        occurred_at: datetime,
    ) -> None:
        self._audit_emitter(
            new_audit_event(
                action=action,
                actor_id=actor_id,
                from_generation=from_generation,
                to_generation=to_generation,
                occurred_at=occurred_at,
            )
        )

    @staticmethod
    def _require_current_generation(
        connection: BitbucketConnection,
        *,
        expected_generation: int,
    ) -> None:
        if connection.generation != expected_generation:
            raise OAuthGenerationRejected(GENERATION_REJECTED_MESSAGE)

    @staticmethod
    def _require_client_credentials_response(
        token_response: Mapping[str, object],
    ) -> tuple[str, int]:
        access_token = token_response.get("access_token")
        token_type = token_response.get("token_type")
        scope = token_response.get("scope")
        expires_in = token_response.get("expires_in")
        if (
            not isinstance(access_token, str)
            or not access_token
            or not isinstance(token_type, str)
            or token_type.casefold() != "bearer"
            or scope != REPOSITORY_SCOPE
            or not isinstance(expires_in, int)
            or isinstance(expires_in, bool)
            or expires_in < 1
        ):
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)
        return access_token, expires_in
