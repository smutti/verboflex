"""Generation-bound, read-only HTTPX adapter for Bitbucket Cloud REST reads."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol, cast

import httpx
from sqlalchemy.orm import Session

from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.urls import (
    repository_metadata_url,
    validate_bitbucket_api_url,
)
from verboflex.services.bitbucket_oauth import (
    REPOSITORY_SCOPE,
    BitbucketCredentialLease,
)

PROVIDER_READ_FAILED_MESSAGE = "Bitbucket provider read failed"


class BitbucketProviderReadError(RuntimeError):
    """Bound every provider, credential, and response failure to one safe message."""


class BitbucketCredentialLeaseAuthority(Protocol):
    """Minimal generation authority consumed by provider reads."""

    def acquire_repository_read_lease(self, session: Session) -> BitbucketCredentialLease:
        """Return one current transient access-token lease."""
        ...

    def require_current_repository_read_lease(
        self,
        session: Session,
        lease: BitbucketCredentialLease,
    ) -> None:
        """Reject a locally revoked or replaced lease."""
        ...


class BitbucketHttpAdapter:
    """Own one pooled client and expose only explicit repository-read capabilities."""

    __slots__ = ("_client", "_credential_leases")

    def __init__(
        self,
        *,
        settings: Settings,
        credential_leases: BitbucketCredentialLeaseAuthority,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        timeout = httpx.Timeout(
            connect=float(settings.bitbucket_http_connect_timeout_seconds),
            read=float(settings.bitbucket_http_read_timeout_seconds),
            write=float(settings.bitbucket_http_write_timeout_seconds),
            pool=float(settings.bitbucket_http_pool_timeout_seconds),
        )
        resolved_transport = transport or httpx.AsyncHTTPTransport(retries=0)
        self._client = httpx.AsyncClient(
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
            timeout=timeout,
            follow_redirects=False,
            transport=resolved_transport,
            trust_env=False,
        )
        self._credential_leases = credential_leases

    async def read_repository_metadata(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
    ) -> Mapping[str, object]:
        """Read one configured repository's metadata through a current lease."""
        url = repository_metadata_url(
            workspace=workspace,
            repository_slug=repository_slug,
        )
        return await self._read_json(session, url=url)

    async def _read_json(self, session: Session, *, url: str) -> Mapping[str, object]:
        validated_url = validate_bitbucket_api_url(url)
        lease = self._credential_leases.acquire_repository_read_lease(session)
        try:
            self._credential_leases.require_current_repository_read_lease(session, lease)
            async with self._client.stream(
                "GET",
                validated_url,
                headers={"Authorization": f"Bearer {lease.access_token}"},
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if location is not None:
                        validate_bitbucket_api_url(location)
                    raise BitbucketProviderReadError(PROVIDER_READ_FAILED_MESSAGE)
                if not 200 <= response.status_code < 300:
                    raise BitbucketProviderReadError(PROVIDER_READ_FAILED_MESSAGE)
                if response.headers.get("x-oauth-scopes") != REPOSITORY_SCOPE:
                    raise BitbucketProviderReadError(PROVIDER_READ_FAILED_MESSAGE)
                payload = await response.aread()
            self._credential_leases.require_current_repository_read_lease(session, lease)
            decoded = json.loads(payload)
            if not isinstance(decoded, dict):
                raise BitbucketProviderReadError(PROVIDER_READ_FAILED_MESSAGE)
            return cast(dict[str, object], decoded)
        except BitbucketProviderReadError:
            raise
        except Exception:
            raise BitbucketProviderReadError(PROVIDER_READ_FAILED_MESSAGE) from None

    async def aclose(self) -> None:
        """Close the one process-scoped connection pool explicitly."""
        await self._client.aclose()


__all__ = [
    "BitbucketCredentialLease",
    "BitbucketHttpAdapter",
    "BitbucketProviderReadError",
]
