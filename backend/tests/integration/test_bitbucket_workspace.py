"""Provider pages stay bounded and within the configured workspace before credentials."""

import asyncio

import httpx
import pytest

from tests.integration.test_bitbucket_http_adapter import FakeCredentialLeaseAuthority
from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter, BitbucketProviderReadError
from verboflex.integrations.bitbucket.urls import BitbucketOperation, validate_bitbucket_api_url


@pytest.mark.parametrize(
    "next_url",
    [
        "https://evil.example/2.0/repositories/acme",
        "https://api.bitbucket.org/2.0/repositories/other?page=2",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile?page=2",
        "https://user:password@api.bitbucket.org/2.0/repositories/acme?page=2",
    ],
)
def test_pagination_scope_is_validated_before_credentials(next_url):
    leases = FakeCredentialLeaseAuthority()
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=leases,
        transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected provider request")),
    )

    async def exercise():
        with pytest.raises(BitbucketProviderReadError):
            await adapter.list_workspace_repositories(object(), workspace="acme", next_url=next_url)
        assert leases.acquired == 0
        await adapter.aclose()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "page",
    [
        {"values": [{}] * 21},
        {"values": {}, "next": None},
        {"values": [], "next": "https://evil.example/2.0/repositories/acme?page=2"},
        {"values": [], "next": "https://api.bitbucket.org/2.0/repositories/other?page=2"},
        {
            "values": [],
            "next": "https://api.bitbucket.org/2.0/repositories/acme?pagelen=20&sort=name",
        },
    ],
)
def test_provider_cannot_increase_page_size_or_redirect_pagination(page):
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=FakeCredentialLeaseAuthority(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json=page, headers={"x-oauth-scopes": "pullrequest:write"}
            )
        ),
    )

    async def exercise():
        with pytest.raises(BitbucketProviderReadError):
            await adapter.list_workspace_repositories(object(), workspace="acme")
        await adapter.aclose()

    asyncio.run(exercise())


def test_workspace_read_is_an_explicit_operation_not_repository_metadata():
    url = "https://api.bitbucket.org/2.0/repositories/acme"
    assert (
        validate_bitbucket_api_url(url, operation=BitbucketOperation.WORKSPACE_REPOSITORIES) == url
    )
    with pytest.raises(ValueError):
        validate_bitbucket_api_url(url, operation=BitbucketOperation.REPOSITORY_METADATA)
