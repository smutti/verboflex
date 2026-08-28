"""Security contract for the generation-bound Bitbucket REST transport."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from verboflex.core.config import Settings

ACCESS_TOKEN = "provider-access-token-must-never-leak"
PROVIDER_BODY = "provider-body-must-never-leak"


@dataclass
class FakeCredentialLeaseAuthority:
    """Expose one observable current generation without a provider dependency."""

    generation: int = 7
    acquired: int = 0
    validated: list[int] = field(default_factory=list)

    def acquire_repository_read_lease(self, _session: object) -> Any:
        """Return the adapter's opaque lease type with a backend-only token."""
        from verboflex.integrations.bitbucket.client import BitbucketCredentialLease

        self.acquired += 1
        return BitbucketCredentialLease(
            generation=self.generation,
            access_token=ACCESS_TOKEN,
        )

    def require_current_repository_read_lease(self, _session: object, lease: Any) -> None:
        """Reject a lease after a local reconnect or revoke generation change."""
        self.validated.append(lease.generation)
        if lease.generation != self.generation:
            raise PermissionError("stale provider generation")


def test_disconnected_lease_fails_as_bounded_provider_state_before_http() -> None:
    """A local revoke is a bounded disconnected read failure, never an HTTP 500."""
    from verboflex.integrations.bitbucket.client import (
        BitbucketHttpAdapter,
        BitbucketProviderReadError,
    )
    from verboflex.services.bitbucket_oauth import OAuthConnectionUnavailable

    class DisconnectedAuthority(FakeCredentialLeaseAuthority):
        def acquire_repository_read_lease(self, _session: object) -> Any:
            raise OAuthConnectionUnavailable("connection unavailable")

    requests: list[httpx.Request] = []
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=DisconnectedAuthority(),
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(200, request=request)
        ),
    )

    async def exercise() -> None:
        with pytest.raises(BitbucketProviderReadError) as captured:
            await adapter.read_repository_metadata(
                object(),
                workspace="acme",
                repository_slug="mobile",
            )
        assert captured.value.kind == "disconnected"
        assert requests == []
        await adapter.aclose()

    asyncio.run(exercise())


def test_reads_metadata_only_through_validated_current_generation() -> None:
    """One metadata read is bounded, host-locked, non-retrying, and secret-safe."""
    try:
        from verboflex.integrations.bitbucket.client import (
            BitbucketHttpAdapter,
            BitbucketProviderReadError,
        )
        from verboflex.integrations.bitbucket.urls import validate_bitbucket_api_url
    except ModuleNotFoundError:
        pytest.fail("safe Bitbucket HTTP adapter is not implemented", pytrace=False)

    requests: list[httpx.Request] = []
    attempts: dict[str, int] = {}

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        slug = request.url.path.rsplit("/", 1)[-1]
        attempts[slug] = attempts.get(slug, 0) + 1
        if slug == "redirected":
            return httpx.Response(
                302,
                headers={"location": "https://attacker.example/steal"},
                request=request,
            )
        if slug == "safe-redirect":
            return httpx.Response(
                302,
                headers={"location": "https://api.bitbucket.org/2.0/repositories/acme/mobile"},
                request=request,
            )
        if slug == "failure":
            return httpx.Response(503, text=PROVIDER_BODY, request=request)
        if slug == "retry":
            raise httpx.ConnectError(PROVIDER_BODY, request=request)
        if slug == "wrong-scope":
            return httpx.Response(
                200,
                json={"uuid": "{repository-uuid}"},
                headers={"x-oauth-scopes": "repository:write"},
                request=request,
            )
        if slug == "non-object":
            return httpx.Response(
                200,
                json=[{"uuid": "{repository-uuid}"}],
                headers={"x-oauth-scopes": "repository"},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "uuid": "{repository-uuid}",
                "workspace": {"slug": "acme"},
                "slug": slug,
            },
            headers={"x-oauth-scopes": "repository"},
            request=request,
        )

    authority = FakeCredentialLeaseAuthority()
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=authority,
        transport=httpx.MockTransport(provider),
    )

    async def exercise() -> None:
        metadata = await adapter.read_repository_metadata(
            object(),
            workspace="acme",
            repository_slug="mobile",
        )
        assert metadata == {
            "uuid": "{repository-uuid}",
            "workspace": {"slug": "acme"},
            "slug": "mobile",
        }

        request = requests[-1]
        assert request.method == "GET"
        assert str(request.url) == "https://api.bitbucket.org/2.0/repositories/acme/mobile"
        assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert request.headers["accept-encoding"] == "identity"
        assert request.extensions["timeout"] == {
            "connect": 3.0,
            "read": 10.0,
            "write": 10.0,
            "pool": 3.0,
        }
        assert authority.acquired == 1
        assert authority.validated == [7, 7]

        calls_before_invalid_urls = len(requests)
        invalid_urls = (
            "http://api.bitbucket.org/2.0/repositories/acme/mobile",
            (
                "https://user:"  # pragma: allowlist secret
                "password@api.bitbucket.org/2.0/repositories/acme/mobile"
            ),
            "https://api.bitbucket.org:443/2.0/repositories/acme/mobile",
            "https://api.bitbucket.org.attacker.example/2.0/repositories/acme/mobile",
            "https://attacker.example/2.0/repositories/acme/mobile",
        )
        for invalid_url in invalid_urls:
            with pytest.raises(ValueError, match="Bitbucket provider URL rejected"):
                validate_bitbucket_api_url(invalid_url)
        assert len(requests) == calls_before_invalid_urls

        for slug in (
            "redirected",
            "safe-redirect",
            "failure",
            "retry",
            "wrong-scope",
            "non-object",
        ):
            with pytest.raises(BitbucketProviderReadError) as captured:
                await adapter.read_repository_metadata(
                    object(),
                    workspace="acme",
                    repository_slug=slug,
                )
            diagnostic = f"{captured.value!r} {captured.value}"
            assert ACCESS_TOKEN not in diagnostic
            assert PROVIDER_BODY not in diagnostic

        assert attempts["redirected"] == 1
        assert attempts["safe-redirect"] == 1
        assert attempts["failure"] == 1
        assert attempts["retry"] == 1
        assert attempts["wrong-scope"] == 1
        assert attempts["non-object"] == 1
        assert all(request.url.host == "api.bitbucket.org" for request in requests)
        await adapter.aclose()

    asyncio.run(exercise())


@pytest.mark.parametrize("invalidate_at", ["before_request", "during_response"])
def test_reconnect_or_revoke_discards_stale_provider_results(invalidate_at: str) -> None:
    """A locally superseded credential can neither start nor finish a provider read."""
    from verboflex.integrations.bitbucket.client import (
        BitbucketHttpAdapter,
        BitbucketProviderReadError,
    )

    requests: list[httpx.Request] = []

    @dataclass
    class InvalidatingCredentialLeaseAuthority(FakeCredentialLeaseAuthority):
        invalidate_after_acquire: bool = False

        def acquire_repository_read_lease(self, session: object) -> Any:
            lease = super().acquire_repository_read_lease(session)
            if self.invalidate_after_acquire:
                self.generation += 1
            return lease

    authority = InvalidatingCredentialLeaseAuthority(
        invalidate_after_acquire=invalidate_at == "before_request"
    )

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if invalidate_at == "during_response":
            authority.generation += 1
        return httpx.Response(
            200,
            json={"uuid": "{stale-repository-uuid}"},
            headers={"x-oauth-scopes": "repository"},
            request=request,
        )

    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=authority,
        transport=httpx.MockTransport(provider),
    )

    async def exercise() -> None:
        with pytest.raises(BitbucketProviderReadError) as captured:
            await adapter.read_repository_metadata(
                object(),
                workspace="acme",
                repository_slug="mobile",
            )
        assert str(captured.value) == "Bitbucket provider read failed"
        assert "stale" not in f"{captured.value!r} {captured.value}".lower()
        assert len(requests) == (0 if invalidate_at == "before_request" else 1)
        await adapter.aclose()

    asyncio.run(exercise())


def test_provider_url_boundary_allows_only_integrated_read_families() -> None:
    """Excluded Bitbucket endpoint families fail before any credential can be sent."""
    from verboflex.integrations.bitbucket.urls import (
        repository_metadata_url,
        validate_bitbucket_api_url,
    )

    allowed_urls = (
        "https://api.bitbucket.org/2.0/repositories/acme/mobile",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/refs/branches?pagelen=100",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/refs/branches/feature%2Fone",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/src/"
        "0123456789abcdef0123456789abcdef01234567/?pagelen=100",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/src/"
        "0123456789abcdef0123456789abcdef01234567/locales/en.json",
    )
    for allowed_url in allowed_urls:
        assert validate_bitbucket_api_url(allowed_url) == allowed_url

    excluded_urls = (
        "https://api.bitbucket.org/2.0/repositories",
        "https://api.bitbucket.org/2.0/repositories/acme",
        "https://api.bitbucket.org/2.0/user",
        "https://api.bitbucket.org/2.0/workspaces/acme/members",
        "https://api.bitbucket.org/2.0/workspaces/acme/projects",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/refs/tags",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/commits",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/diff/abc..def",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/commit/abc/statuses",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/pullrequests",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/hooks",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/permissions-config",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/branch-restrictions",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/deploy-keys",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/pipelines",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/deployments",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/issues",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/downloads",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/wiki",
        "https://api.bitbucket.org/2.0/snippets/acme",
        "https://api.bitbucket.org/2.0/workspaces/acme/search/code",
        "https://bitbucket.org/site/oauth2/revoke",
    )
    for excluded_url in excluded_urls:
        with pytest.raises(ValueError, match="Bitbucket provider URL rejected"):
            validate_bitbucket_api_url(excluded_url)

    structurally_invalid_urls: tuple[object, ...] = (
        None,
        "",
        "https://api.bitbucket.org\\2.0\\repositories\\acme\\mobile",
        "https://api.bitbucket.org:not-a-port/2.0/repositories/acme/mobile",
    )
    for invalid_url in structurally_invalid_urls:
        with pytest.raises(ValueError, match="Bitbucket provider URL rejected"):
            validate_bitbucket_api_url(invalid_url)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Bitbucket provider URL rejected"):
        repository_metadata_url(workspace="Acme", repository_slug="mobile")


def test_oauth_credential_lease_authority_fails_closed_for_unreadable_rows() -> None:
    """The real lease authority decrypts only readable rows and rechecks generation."""
    from verboflex.security.secret_box import SecretBoxDecryptionError
    from verboflex.services.bitbucket_oauth import (
        BitbucketOAuthService,
        OAuthConnectionUnavailable,
        OAuthGenerationRejected,
    )

    @dataclass
    class FakeSession:
        connection: object | None

        def begin(self) -> Any:
            return nullcontext()

        def get(self, _model: object, _identity: int) -> object | None:
            return self.connection

    class ReadableSecretBox:
        def decrypt(self, ciphertext: str) -> str:
            assert ciphertext == "encrypted-access-token"
            return ACCESS_TOKEN

    service = object.__new__(BitbucketOAuthService)
    service._secret_box = ReadableSecretBox()
    connection = SimpleNamespace(
        generation=7,
        revoked_at=None,
        scope_profile="repository",
        access_token_ciphertext="encrypted-access-token",
        refresh_token_ciphertext="encrypted-refresh-token",
    )
    session = FakeSession(connection)
    lease = service.acquire_repository_read_lease(session)  # type: ignore[arg-type]
    assert lease.generation == 7
    assert lease.access_token == ACCESS_TOKEN
    service.require_current_repository_read_lease(session, lease)  # type: ignore[arg-type]

    connection.generation = 8
    with pytest.raises(OAuthGenerationRejected, match="generation rejected"):
        service.require_current_repository_read_lease(session, lease)  # type: ignore[arg-type]

    unreadable_connections = (
        None,
        SimpleNamespace(**{**vars(connection), "revoked_at": object()}),
        SimpleNamespace(**{**vars(connection), "scope_profile": "repository:write"}),
        SimpleNamespace(**{**vars(connection), "access_token_ciphertext": None}),
        SimpleNamespace(**{**vars(connection), "refresh_token_ciphertext": None}),
    )
    for unreadable_connection in unreadable_connections:
        with pytest.raises(OAuthConnectionUnavailable, match="connection unavailable"):
            service.acquire_repository_read_lease(  # type: ignore[arg-type]
                FakeSession(unreadable_connection)
            )

    class RejectingSecretBox:
        def decrypt(self, _ciphertext: str) -> str:
            raise SecretBoxDecryptionError("invalid ciphertext")

    service._secret_box = RejectingSecretBox()
    connection.generation = 7
    with pytest.raises(OAuthConnectionUnavailable, match="connection unavailable"):
        service.acquire_repository_read_lease(FakeSession(connection))  # type: ignore[arg-type]
