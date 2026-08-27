"""Provider-bound contracts for live Bitbucket repository discovery."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.client import (
    BitbucketHttpAdapter,
    BitbucketProviderReadError,
)

ACCESS_TOKEN = "discovery-provider-token"


@dataclass
class FakeCredentialLeaseAuthority:
    """Expose one observable current generation without external credentials."""

    generation: int = 7
    acquired: int = 0
    validated: list[int] = field(default_factory=list)

    def acquire_repository_read_lease(self, _session: object) -> Any:
        from verboflex.integrations.bitbucket.client import BitbucketCredentialLease

        self.acquired += 1
        return BitbucketCredentialLease(generation=self.generation, access_token=ACCESS_TOKEN)

    def require_current_repository_read_lease(self, _session: object, lease: Any) -> None:
        self.validated.append(lease.generation)
        if lease.generation != self.generation:
            raise PermissionError("stale provider generation")


def test_lists_exact_branches_with_validated_opaque_pagination() -> None:
    """Provider order and spelling survive pagelen=100 traversal without URL leakage."""
    requests: list[httpx.Request] = []
    second_page = (
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/refs/branches"
        "?pagelen=100&after=opaque-provider-position"
    )

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.params.get("after") is None:
            payload = {
                "values": [
                    {"name": "Main", "target": {"hash": "a" * 40}},
                    {"name": "feature/ExactCase", "target": {"hash": "b" * 40}},
                ],
                "next": second_page,
            }
        else:
            payload = {
                "values": [
                    {"name": "release-Ä", "target": {"hash": "c" * 40}},
                ]
            }
        return httpx.Response(
            200,
            json=payload,
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
        branches = await adapter.list_repository_branches(
            object(),
            workspace="acme",
            repository_slug="mobile",
        )
        assert [branch.name for branch in branches] == [
            "Main",
            "feature/ExactCase",
            "release-Ä",
        ]
        assert [branch.commit_hash for branch in branches] == ["a" * 40, "b" * 40, "c" * 40]
        assert [str(request.url) for request in requests] == [
            "https://api.bitbucket.org/2.0/repositories/acme/mobile/refs/branches?pagelen=100",
            second_page,
        ]
        assert all(request.url.host == "api.bitbucket.org" for request in requests)

        requests_before_rejection = len(requests)

        def hostile_provider(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "values": [{"name": "main", "target": {"hash": "d" * 40}}],
                    "next": "https://attacker.example/steal-provider-token",
                },
                headers={"x-oauth-scopes": "repository"},
                request=request,
            )

        hostile = BitbucketHttpAdapter(
            settings=Settings(),
            credential_leases=authority,
            transport=httpx.MockTransport(hostile_provider),
        )
        with pytest.raises(BitbucketProviderReadError) as captured:
            await hostile.list_repository_branches(
                object(),
                workspace="acme",
                repository_slug="mobile",
            )
        assert str(captured.value) == "Bitbucket provider read failed"
        assert "attacker" not in repr(captured.value).lower()
        assert len(requests) == requests_before_rejection + 1
        await hostile.aclose()
        await adapter.aclose()

    asyncio.run(exercise())
