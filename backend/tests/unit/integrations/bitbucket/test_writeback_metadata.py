"""Exact read-only metadata capability, with no optimistic regular-file inference."""

import asyncio

import httpx
import pytest

from tests.integration.test_bitbucket_http_adapter import FakeCredentialLeaseAuthority
from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter, BitbucketProviderReadError
from verboflex.integrations.bitbucket.urls import BitbucketOperation, validate_bitbucket_api_url


def _payload():
    return {
        "type": "commit_file",
        "path": "i18n/en.json",
        "commit": {"hash": "a" * 40},
        "size": 16,
        "attributes": [],
    }


def _read(payload, *, status=200):
    requests = []
    leases = FakeCredentialLeaseAuthority()

    def respond(request):
        requests.append(request)
        return httpx.Response(
            status,
            json=payload,
            headers={"x-oauth-scopes": "pullrequest:write", "location": "https://evil.test/secret"},
            request=request,
        )

    async def run():
        adapter = BitbucketHttpAdapter(
            settings=Settings(), credential_leases=leases, transport=httpx.MockTransport(respond)
        )
        try:
            return await adapter.read_repository_source_metadata(
                object(),
                workspace="acme",
                repository_slug="app",
                commit_hash="a" * 40,
                path="i18n/en.json",
            )
        finally:
            await adapter.aclose()

    return asyncio.run(run()), requests, leases


def test_exact_metadata_is_generation_checked_and_get_only():
    result, requests, leases = _read(_payload())
    assert (result.path, result.commit_hash, result.size_bytes, result.attributes) == (
        "i18n/en.json",
        "a" * 40,
        16,
        (),
    )
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url).endswith("/src/" + "a" * 40 + "/i18n/en.json?format=meta")
    assert leases.validated == [7, 7]


@pytest.mark.parametrize(
    "change",
    [
        {"path": "other.json"},
        {"commit": {"hash": "b" * 40}},
        {"type": "commit_directory"},
        {"attributes": None},
        {"attributes": ["binary", "binary"]},
        {"attributes": ["unknown"]},
        {"size": True},
        {"size": -1},
        {"size": "16"},
    ],
)
def test_metadata_identity_mismatch(change):
    with pytest.raises(BitbucketProviderReadError, match="Bitbucket provider read failed") as error:
        _read(_payload() | change)
    assert error.value.kind == "invalid_source"


def test_missing_attributes_are_not_regular():
    payload = _payload()
    del payload["attributes"]
    with pytest.raises(BitbucketProviderReadError):
        _read(payload)


def test_metadata_redirect_is_rejected():
    with pytest.raises(BitbucketProviderReadError) as error:
        _read(_payload(), status=302)
    assert error.value.kind == "invalid_source"


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "?format=raw",
        "?format=meta&format=meta",
        "?format=meta&pagelen=100",
        "?format=%6deta",
        "?format=meta#x",
    ],
)
def test_metadata_query_injection_is_rejected(suffix):
    with pytest.raises(ValueError):
        validate_bitbucket_api_url(
            "https://api.bitbucket.org/2.0/repositories/acme/app/src/"
            + "a" * 40
            + "/i18n/en.json"
            + suffix,
            operation=BitbucketOperation.SOURCE_METADATA,
        )


def test_metadata_host_injection_is_rejected():
    with pytest.raises(ValueError):
        validate_bitbucket_api_url(
            "https://api.bitbucket.org.evil.test/2.0/repositories/acme/app/src/"
            + "a" * 40
            + "/i18n/en.json?format=meta",
            operation=BitbucketOperation.SOURCE_METADATA,
        )


def test_metadata_requires_a_file_path_not_a_commit_root():
    with pytest.raises(ValueError):
        validate_bitbucket_api_url(
            "https://api.bitbucket.org/2.0/repositories/acme/app/src/" + "a" * 40 + "?format=meta",
            operation=BitbucketOperation.SOURCE_METADATA,
        )
