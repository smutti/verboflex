"""Generation-bound, read-only HTTPX adapter for Bitbucket Cloud REST reads."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, cast

import httpx
from sqlalchemy.orm import Session

from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.urls import (
    repository_branches_url,
    repository_metadata_url,
    validate_bitbucket_api_url,
)
from verboflex.services.bitbucket_oauth import (
    REPOSITORY_SCOPE,
    BitbucketCredentialLease,
    OAuthConnectionUnavailable,
    OAuthGenerationRejected,
)

PROVIDER_READ_FAILED_MESSAGE = "Bitbucket provider read failed"


ProviderFailureKind = Literal[
    "disconnected",
    "reauthorization_required",
    "permission_denied",
    "not_found",
    "unavailable",
    "timeout",
]


class BitbucketProviderReadError(RuntimeError):
    """Bound every provider, credential, and response failure to one safe message."""

    def __init__(self, *, kind: ProviderFailureKind = "unavailable") -> None:
        super().__init__(PROVIDER_READ_FAILED_MESSAGE)
        self.kind = kind


@dataclass(frozen=True, slots=True)
class BitbucketBranch:
    """One exact provider branch and its current target commit."""

    name: str
    commit_hash: str


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

    async def list_repository_branches(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
    ) -> tuple[BitbucketBranch, ...]:
        """Traverse opaque provider pages in order and preserve exact branch names."""
        next_url: str | None = repository_branches_url(
            workspace=workspace,
            repository_slug=repository_slug,
        )
        branches: list[BitbucketBranch] = []
        visited: set[str] = set()
        while next_url is not None:
            if next_url in visited or len(visited) >= 50:
                raise BitbucketProviderReadError()
            visited.add(next_url)
            page = await self._read_json(session, url=next_url)
            values = page.get("values")
            if not isinstance(values, list):
                raise BitbucketProviderReadError()
            for raw_branch in values:
                branch = self._parse_branch(raw_branch)
                branches.append(branch)
            raw_next = page.get("next")
            if raw_next is None:
                next_url = None
            elif isinstance(raw_next, str):
                try:
                    next_url = validate_bitbucket_api_url(raw_next)
                except ValueError:
                    raise BitbucketProviderReadError() from None
            else:
                raise BitbucketProviderReadError()
        return tuple(branches)

    @staticmethod
    def _parse_branch(raw_branch: object) -> BitbucketBranch:
        if not isinstance(raw_branch, dict):
            raise BitbucketProviderReadError()
        name = raw_branch.get("name")
        target = raw_branch.get("target")
        commit_hash = target.get("hash") if isinstance(target, dict) else None
        if (
            not isinstance(name, str)
            or not name
            or len(name) > 255
            or not isinstance(commit_hash, str)
            or len(commit_hash) != 40
            or any(character not in "0123456789abcdefABCDEF" for character in commit_hash)
        ):
            raise BitbucketProviderReadError()
        return BitbucketBranch(name=name, commit_hash=commit_hash)

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
                    raise BitbucketProviderReadError()
                if not 200 <= response.status_code < 300:
                    kind: ProviderFailureKind
                    if response.status_code == 401:
                        kind = "reauthorization_required"
                    elif response.status_code == 403:
                        kind = "permission_denied"
                    elif response.status_code == 404:
                        kind = "not_found"
                    elif response.status_code in {408, 504}:
                        kind = "timeout"
                    else:
                        kind = "unavailable"
                    raise BitbucketProviderReadError(kind=kind)
                if response.headers.get("x-oauth-scopes") != REPOSITORY_SCOPE:
                    raise BitbucketProviderReadError(kind="permission_denied")
                payload = await response.aread()
            self._credential_leases.require_current_repository_read_lease(session, lease)
            decoded = json.loads(payload)
            if not isinstance(decoded, dict):
                raise BitbucketProviderReadError()
            return cast(dict[str, object], decoded)
        except BitbucketProviderReadError:
            raise
        except OAuthConnectionUnavailable:
            raise BitbucketProviderReadError(kind="disconnected") from None
        except OAuthGenerationRejected:
            raise BitbucketProviderReadError(kind="reauthorization_required") from None
        except httpx.TimeoutException:
            raise BitbucketProviderReadError(kind="timeout") from None
        except Exception:
            raise BitbucketProviderReadError() from None

    async def aclose(self) -> None:
        """Close the one process-scoped connection pool explicitly."""
        await self._client.aclose()


__all__ = [
    "BitbucketCredentialLease",
    "BitbucketBranch",
    "BitbucketHttpAdapter",
    "BitbucketProviderReadError",
]
