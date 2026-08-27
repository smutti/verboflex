"""Security contract for the generation-bound Bitbucket REST transport."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
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
        if slug == "failure":
            return httpx.Response(503, text=PROVIDER_BODY, request=request)
        if slug == "retry":
            raise httpx.ConnectError(PROVIDER_BODY, request=request)
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
            "https://user:password@api.bitbucket.org/2.0/repositories/acme/mobile",
            "https://api.bitbucket.org:443/2.0/repositories/acme/mobile",
            "https://api.bitbucket.org.attacker.example/2.0/repositories/acme/mobile",
            "https://attacker.example/2.0/repositories/acme/mobile",
        )
        for invalid_url in invalid_urls:
            with pytest.raises(ValueError, match="Bitbucket provider URL rejected"):
                validate_bitbucket_api_url(invalid_url)
        assert len(requests) == calls_before_invalid_urls

        for slug in ("redirected", "failure", "retry"):
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
        assert attempts["failure"] == 1
        assert attempts["retry"] == 1
        assert all(request.url.host == "api.bitbucket.org" for request in requests)
        await adapter.aclose()

    asyncio.run(exercise())
