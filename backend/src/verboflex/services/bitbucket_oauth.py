"""Single-use, generation-bound Bitbucket OAuth connection authority."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from base64 import b64encode
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
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

OAUTH_STATE_BYTES = 32
OAUTH_STATE_TTL_SECONDS = 600
OAUTH_STATE_KEY_PREFIX = "verboflex:bitbucket:oauth-state:"
REPOSITORY_SCOPE = "repository"
CALLBACK_REJECTED_MESSAGE = "OAuth callback rejected"
SETTINGS_REQUIRED_MESSAGE = "Bitbucket OAuth settings are required"
INVALID_KEYRING_MESSAGE = "Bitbucket token encryption keyring is invalid"
GENERATION_REJECTED_MESSAGE = "Bitbucket connection generation rejected"
CONNECTION_UNAVAILABLE_MESSAGE = "Bitbucket connection unavailable"
BITBUCKET_AUTHORIZE_URL = "https://bitbucket.org/site/oauth2/authorize"
BITBUCKET_TOKEN_URL = "https://bitbucket.org/site/oauth2/access_token"
TOKEN_EXCHANGE_TIMEOUT_SECONDS = 10
MAX_TOKEN_RESPONSE_BYTES = 65_536


class RedisOAuthStateClient(Protocol):
    """Minimal Redis capability for one expiring OAuth binding."""

    def set(self, name: str, value: str, *, ex: int, nx: bool) -> object:
        """Store an expiring binding only when its digest is unused."""
        ...

    def getdel(self, name: str) -> object:
        """Atomically consume one binding."""
        ...


class TokenExchange(Protocol):
    """Backend-only authorization-code exchange boundary."""

    def exchange_authorization_code(
        self,
        *,
        code: str,
        callback_uri: str,
        client_id: str,
        client_secret: str,
    ) -> Mapping[str, object]:
        """Exchange one code without exposing provider material to the browser."""
        ...

    def refresh_tokens(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> Mapping[str, object]:
        """Exchange one current rotating refresh token for one complete pair."""
        ...


class OAuthCallbackRejected(PermissionError):
    """Stable non-enumerating callback denial."""


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
    """Bounded standard-library adapter for Bitbucket's exact OAuth token endpoint."""

    def __init__(self, *, opener: OpenerDirector | None = None) -> None:
        self._opener = opener or build_opener(_RejectRedirects())

    def exchange_authorization_code(
        self,
        *,
        code: str,
        callback_uri: str,
        client_id: str,
        client_secret: str,
    ) -> Mapping[str, object]:
        return self._exchange(
            fields={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": callback_uri,
            },
            client_id=client_id,
            client_secret=client_secret,
        )

    def refresh_tokens(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> Mapping[str, object]:
        return self._exchange(
            fields={"grant_type": "refresh_token", "refresh_token": refresh_token},
            client_id=client_id,
            client_secret=client_secret,
        )

    def _exchange(
        self,
        *,
        fields: Mapping[str, str],
        client_id: str,
        client_secret: str,
    ) -> Mapping[str, object]:
        credentials = b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
        request = Request(
            BITBUCKET_TOKEN_URL,
            data=urlencode(fields).encode("ascii"),
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
            raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE) from error
        if len(payload) > MAX_TOKEN_RESPONSE_BYTES:
            raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE)
        try:
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE) from error
        if not isinstance(decoded, dict):
            raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE)
        return cast(dict[str, object], decoded)


@dataclass(frozen=True, slots=True)
class BitbucketConnectionStatus:
    """Bounded provider state safe for later API projection."""

    state: str
    generation: int
    scope_profile: str


@dataclass(frozen=True, slots=True)
class OAuthCallbackResult:
    """Fixed redirect and bounded status returned after connection."""

    redirect_path: str
    status: BitbucketConnectionStatus


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
class _OAuthStateBinding:
    admin_id: str
    session_id: str
    expected_generation: int
    callback_uri: str
    post_callback_path: str


class BitbucketOAuthService:
    """Own OAuth state consumption and encrypted singleton persistence."""

    def __init__(
        self,
        *,
        settings: Settings,
        redis_client: RedisOAuthStateClient,
        token_exchange: TokenExchange,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
        audit_emitter: AuditEventEmitter = emit_audit_event,
    ) -> None:
        self._settings = settings
        self._redis = redis_client
        self._token_exchange = token_exchange
        self._random_bytes = random_bytes
        self._audit_emitter = audit_emitter
        self._client_id, self._client_secret, self._callback_uri = self._require_oauth_settings(
            settings
        )
        self._secret_box = self._build_secret_box(settings)

    @staticmethod
    def _require_oauth_settings(settings: Settings) -> tuple[str, str, str]:
        client_id = settings.bitbucket_oauth_client_id
        client_secret = settings.bitbucket_oauth_client_secret
        callback_uri = settings.bitbucket_oauth_callback_uri
        if client_id is None or client_secret is None or callback_uri is None:
            raise ValueError(SETTINGS_REQUIRED_MESSAGE)
        normalized_client_id = client_id.strip()
        normalized_client_secret = client_secret.get_secret_value()
        if not normalized_client_id or not normalized_client_secret:
            raise ValueError(SETTINGS_REQUIRED_MESSAGE)
        return normalized_client_id, normalized_client_secret, str(callback_uri)

    @staticmethod
    def _build_secret_box(settings: Settings) -> SecretBox:
        keyring = settings.bitbucket_token_encryption_keyring
        if keyring is None:
            raise ValueError(SETTINGS_REQUIRED_MESSAGE)
        try:
            return SecretBox.from_keyring(keyring.get_secret_value())
        except SecretBoxConfigurationError as error:
            raise ValueError(INVALID_KEYRING_MESSAGE) from error

    @staticmethod
    def _state_key(state: str) -> str:
        digest = hashlib.sha256(state.encode()).hexdigest()
        return f"{OAUTH_STATE_KEY_PREFIX}{digest}"

    def start(
        self,
        *,
        admin_id: UUID,
        session_id: UUID,
        expected_generation: int,
    ) -> str:
        """Create one opaque state and persist only its digest-bound authority."""
        raw_state = self._random_bytes(OAUTH_STATE_BYTES)
        if len(raw_state) != OAUTH_STATE_BYTES or expected_generation < 0:
            raise ValueError(CALLBACK_REJECTED_MESSAGE)
        state = base64.urlsafe_b64encode(raw_state).rstrip(b"=").decode("ascii")
        binding = _OAuthStateBinding(
            admin_id=str(admin_id),
            session_id=str(session_id),
            expected_generation=expected_generation,
            callback_uri=self._callback_uri,
            post_callback_path=self._settings.bitbucket_oauth_post_callback_path,
        )
        stored = self._redis.set(
            self._state_key(state),
            json.dumps(asdict(binding), separators=(",", ":"), sort_keys=True),
            ex=OAUTH_STATE_TTL_SECONDS,
            nx=True,
        )
        if stored is not True:
            raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE)
        return state

    def start_current(
        self,
        session: Session,
        *,
        admin_id: UUID,
        session_id: UUID,
    ) -> str:
        """Bind a new authorization flow to the current durable generation."""
        with session.begin():
            connection = session.get(BitbucketConnection, 1)
            if connection is None:
                raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)
            generation = connection.generation
        return self.start(
            admin_id=admin_id,
            session_id=session_id,
            expected_generation=generation,
        )

    def authorization_url(self, state: str) -> str:
        """Build the exact static-consumer authorization request without scope expansion."""
        query = urlencode(
            {
                "client_id": self._client_id,
                "response_type": "code",
                "state": state,
            }
        )
        return f"{BITBUCKET_AUTHORIZE_URL}?{query}"

    def public_status(self, session: Session) -> BitbucketConnectionPublicStatus:
        """Read one bounded status without decrypting or exposing credential metadata."""
        with session.begin():
            connection = session.get(BitbucketConnection, 1)
            if connection is None:
                return BitbucketConnectionPublicStatus(
                    state="unavailable",
                    connected_at=None,
                    expires_at=None,
                    revoked_at=None,
                )
            has_access = connection.access_token_ciphertext is not None
            has_refresh = connection.refresh_token_ciphertext is not None
            if has_access != has_refresh:
                state: Literal[
                    "disconnected",
                    "connected",
                    "reauthorization_required",
                    "unavailable",
                ] = "unavailable"
            elif connection.revoked_at is not None or not has_access:
                state = "disconnected"
            else:
                state = "connected"
            return BitbucketConnectionPublicStatus(
                state=state,
                connected_at=connection.connected_at,
                expires_at=connection.provider_expires_at,
                revoked_at=connection.revoked_at,
            )

    def acquire_repository_read_lease(self, session: Session) -> BitbucketCredentialLease:
        """Decrypt one current access token without holding a lock across provider I/O."""
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

    @staticmethod
    def require_current_repository_read_lease(
        session: Session,
        lease: BitbucketCredentialLease,
    ) -> None:
        """Reject provider work whose credential generation was locally superseded."""
        with session.begin():
            connection = session.get(BitbucketConnection, 1)
            BitbucketOAuthService._require_readable_connection(connection)
            assert connection is not None
            if connection.generation != lease.generation:
                raise OAuthGenerationRejected(GENERATION_REJECTED_MESSAGE)

    @staticmethod
    def _require_readable_connection(connection: BitbucketConnection | None) -> None:
        if (
            connection is None
            or connection.revoked_at is not None
            or connection.scope_profile != REPOSITORY_SCOPE
            or connection.access_token_ciphertext is None
            or connection.refresh_token_ciphertext is None
        ):
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)

    def complete_callback(
        self,
        session: Session,
        *,
        state: object,
        code: object,
        admin_id: object,
        session_id: object,
        callback_uri: object,
        post_callback_path: object,
    ) -> OAuthCallbackResult:
        """Consume, validate, exchange, and persist one exact-scope generation."""
        binding = self._consume_binding(state)
        self._require_binding(
            binding,
            code=code,
            admin_id=admin_id,
            session_id=session_id,
            callback_uri=callback_uri,
            post_callback_path=post_callback_path,
        )
        return self._complete_bound_callback(session, binding=binding, code=code)

    def complete_callback_from_state(
        self,
        session: Session,
        *,
        state: object,
        code: object,
        callback_uri: object,
        post_callback_path: object,
    ) -> OAuthCallbackResult:
        """Complete a callback using only the consumed state as user authority."""
        binding = self._consume_binding(state)
        self._require_callback_destination(
            binding,
            code=code,
            callback_uri=callback_uri,
            post_callback_path=post_callback_path,
        )
        return self._complete_bound_callback(session, binding=binding, code=code)

    def _complete_bound_callback(
        self,
        session: Session,
        *,
        binding: _OAuthStateBinding,
        code: object,
    ) -> OAuthCallbackResult:
        connected_at = datetime.now(UTC)
        with session.begin():
            connection = self._lock_connection(session)
            if connection.generation != binding.expected_generation:
                raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE)
            token_response = self._exchange(code)
            access_token, refresh_token, expires_in = self._require_token_response(token_response)
            previous_generation = connection.generation
            connection.generation += 1
            connection.access_token_ciphertext = self._secret_box.encrypt(access_token)
            connection.refresh_token_ciphertext = self._secret_box.encrypt(refresh_token)
            connection.scope_profile = REPOSITORY_SCOPE
            connection.provider_expires_at = connected_at + timedelta(seconds=expires_in)
            connection.connected_at = connected_at
            connection.revoked_at = None
            session.flush()
            status = BitbucketConnectionStatus(
                state="connected",
                generation=connection.generation,
                scope_profile=REPOSITORY_SCOPE,
            )
        self._emit_lifecycle_event(
            action="bitbucket.connected",
            actor_id=UUID(binding.admin_id),
            from_generation=previous_generation,
            to_generation=status.generation,
            occurred_at=connected_at,
        )
        return OAuthCallbackResult(
            redirect_path=self._settings.bitbucket_oauth_post_callback_path,
            status=status,
        )

    def refresh(
        self,
        session: Session,
        *,
        expected_generation: int,
        actor_id: UUID,
    ) -> BitbucketConnectionStatus:
        """Rotate one current provider pair while holding the singleton lock."""
        refreshed_at = datetime.now(UTC)
        with session.begin():
            connection = self._lock_connection(session)
            self._require_current_generation(
                connection,
                expected_generation=expected_generation,
            )
            if (
                connection.access_token_ciphertext is None
                or connection.refresh_token_ciphertext is None
                or connection.revoked_at is not None
            ):
                raise OAuthGenerationRejected(GENERATION_REJECTED_MESSAGE)
            try:
                refresh_token = self._secret_box.decrypt(connection.refresh_token_ciphertext)
            except SecretBoxDecryptionError as error:
                raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE) from error
            try:
                token_response = self._token_exchange.refresh_tokens(
                    refresh_token=refresh_token,
                    client_id=self._client_id,
                    client_secret=self._client_secret,
                )
                access_token, rotated_refresh_token, expires_in = self._require_token_response(
                    token_response
                )
            except OAuthCallbackRejected as error:
                raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE) from error
            except Exception as error:
                raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE) from error

            previous_generation = connection.generation
            connection.generation += 1
            connection.access_token_ciphertext = self._secret_box.encrypt(access_token)
            connection.refresh_token_ciphertext = self._secret_box.encrypt(rotated_refresh_token)
            connection.scope_profile = REPOSITORY_SCOPE
            connection.provider_expires_at = refreshed_at + timedelta(seconds=expires_in)
            connection.revoked_at = None
            session.flush()
            status = BitbucketConnectionStatus(
                state="connected",
                generation=connection.generation,
                scope_profile=REPOSITORY_SCOPE,
            )
        self._emit_lifecycle_event(
            action="bitbucket.refreshed",
            actor_id=actor_id,
            from_generation=previous_generation,
            to_generation=status.generation,
            occurred_at=refreshed_at,
        )
        return status

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
        """Apply the sole local invalidation transition under the singleton lock."""
        revoked_at = datetime.now(UTC)
        changed = False
        with session.begin():
            connection = self._lock_connection(session)
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
                if expected_generation is not None:
                    self._require_current_generation(
                        connection,
                        expected_generation=expected_generation,
                    )
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
        if changed:
            self._emit_lifecycle_event(
                action="bitbucket.revoked",
                actor_id=actor_id,
                from_generation=previous_generation,
                to_generation=status.generation,
                occurred_at=revoked_at,
            )
        return status

    @staticmethod
    def _lock_connection(session: Session) -> BitbucketConnection:
        connection = session.execute(
            select(BitbucketConnection).where(BitbucketConnection.id == 1).with_for_update()
        ).scalar_one_or_none()
        if connection is None:
            raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)
        return connection

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

    def _consume_binding(self, state: object) -> _OAuthStateBinding:
        if not isinstance(state, str) or not state:
            raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE)
        try:
            raw_binding = self._redis.getdel(self._state_key(state))
            if not isinstance(raw_binding, (str, bytes)):
                raise ValueError
            payload = json.loads(raw_binding)
            if not isinstance(payload, dict) or set(payload) != {
                "admin_id",
                "session_id",
                "expected_generation",
                "callback_uri",
                "post_callback_path",
            }:
                raise ValueError
            return _OAuthStateBinding(**payload)
        except Exception:
            raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE) from None

    @staticmethod
    def _require_binding(
        binding: _OAuthStateBinding,
        *,
        code: object,
        admin_id: object,
        session_id: object,
        callback_uri: object,
        post_callback_path: object,
    ) -> None:
        if (
            not isinstance(code, str)
            or not code
            or str(admin_id) != binding.admin_id
            or str(session_id) != binding.session_id
            or callback_uri != binding.callback_uri
            or post_callback_path != binding.post_callback_path
        ):
            raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE)

    @staticmethod
    def _require_callback_destination(
        binding: _OAuthStateBinding,
        *,
        code: object,
        callback_uri: object,
        post_callback_path: object,
    ) -> None:
        if (
            not isinstance(code, str)
            or not code
            or callback_uri != binding.callback_uri
            or post_callback_path != binding.post_callback_path
        ):
            raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE)

    def _exchange(self, code: object) -> Mapping[str, object]:
        assert isinstance(code, str)
        try:
            return self._token_exchange.exchange_authorization_code(
                code=code,
                callback_uri=self._callback_uri,
                client_id=self._client_id,
                client_secret=self._client_secret,
            )
        except Exception:
            raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE) from None

    @staticmethod
    def _require_token_response(
        token_response: Mapping[str, object],
    ) -> tuple[str, str, int]:
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        scope = token_response.get("scope")
        expires_in = token_response.get("expires_in")
        if (
            not isinstance(access_token, str)
            or not access_token
            or not isinstance(refresh_token, str)
            or not refresh_token
            or scope != REPOSITORY_SCOPE
            or not isinstance(expires_in, int)
            or isinstance(expires_in, bool)
            or expires_in < 1
        ):
            raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE)
        return access_token, refresh_token, expires_in
