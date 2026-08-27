"""Single-use, generation-bound Bitbucket OAuth connection authority."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from cryptography.fernet import Fernet, MultiFernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.core.config import Settings
from verboflex.models.bitbucket_connection import BitbucketConnection

OAUTH_STATE_BYTES = 32
OAUTH_STATE_TTL_SECONDS = 600
OAUTH_STATE_KEY_PREFIX = "verboflex:bitbucket:oauth-state:"
REPOSITORY_SCOPE = "repository"
CALLBACK_REJECTED_MESSAGE = "OAuth callback rejected"
SETTINGS_REQUIRED_MESSAGE = "Bitbucket OAuth settings are required"
INVALID_KEYRING_MESSAGE = "Bitbucket token encryption keyring is invalid"


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


class OAuthCallbackRejected(PermissionError):
    """Stable non-enumerating callback denial."""


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
    ) -> None:
        self._settings = settings
        self._redis = redis_client
        self._token_exchange = token_exchange
        self._random_bytes = random_bytes
        self._client_id, self._client_secret, self._callback_uri = (
            self._require_oauth_settings(settings)
        )
        self._cipher = self._build_cipher(settings)

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
    def _build_cipher(settings: Settings) -> MultiFernet:
        keyring = settings.bitbucket_token_encryption_keyring
        if keyring is None:
            raise ValueError(SETTINGS_REQUIRED_MESSAGE)
        raw_keys = keyring.get_secret_value().split(",")
        if not raw_keys or any(not key for key in raw_keys):
            raise ValueError(INVALID_KEYRING_MESSAGE)
        try:
            return MultiFernet([Fernet(key.encode()) for key in raw_keys])
        except (TypeError, ValueError) as error:
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
        with session.begin():
            connection = session.execute(
                select(BitbucketConnection).where(BitbucketConnection.id == 1).with_for_update()
            ).scalar_one()
            if connection.generation != binding.expected_generation:
                raise OAuthCallbackRejected(CALLBACK_REJECTED_MESSAGE)
            token_response = self._exchange(code)
            access_token, refresh_token, expires_in = self._require_token_response(
                token_response
            )
            connected_at = datetime.now(UTC)
            connection.generation += 1
            connection.access_token_ciphertext = self._cipher.encrypt(
                access_token.encode()
            ).decode()
            connection.refresh_token_ciphertext = self._cipher.encrypt(
                refresh_token.encode()
            ).decode()
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
        return OAuthCallbackResult(
            redirect_path=self._settings.bitbucket_oauth_post_callback_path,
            status=status,
        )

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
