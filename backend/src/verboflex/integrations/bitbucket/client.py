"""Generation-bound, read-only HTTPX adapter for Bitbucket Cloud REST reads."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, cast
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.urls import (
    repository_branch_url,
    repository_branches_url,
    repository_metadata_url,
    repository_source_url,
    validate_bitbucket_api_url,
    validate_repository_relative_path,
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
    "invalid_source",
    "limit_exceeded",
]

_MAX_JSON_RESPONSE_BYTES = 1_048_576


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


@dataclass(frozen=True, slots=True)
class BitbucketSourceEntry:
    """One provider source-tree entry with a normalized repository path."""

    path: str
    kind: Literal["file", "directory"]
    size: int | None


@dataclass(frozen=True, slots=True)
class BitbucketSourcePage:
    """One source-tree page and its validated opaque continuation URL."""

    entries: tuple[BitbucketSourceEntry, ...]
    next_url: str | None


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
            page_branches, next_url = self._parse_branch_page(page)
            branches.extend(page_branches)
        return tuple(branches)

    async def resolve_repository_branch(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        branch: str,
    ) -> BitbucketBranch:
        """Resolve one exact branch name to its current immutable commit hash."""
        url = repository_branch_url(
            workspace=workspace,
            repository_slug=repository_slug,
            branch=branch,
        )
        resolved = self._parse_branch(await self._read_json(session, url=url))
        if resolved.name != branch:
            raise BitbucketProviderReadError(kind="invalid_source")
        return resolved

    async def list_repository_source_page(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        commit_hash: str,
        directory_path: str | None,
        next_url: str | None = None,
    ) -> BitbucketSourcePage:
        """Read one commit-bound directory page through a validated continuation."""
        source_url = repository_source_url(
            workspace=workspace,
            repository_slug=repository_slug,
            commit_hash=commit_hash,
            path=directory_path,
            paginated=True,
        )
        url = next_url or source_url
        if urlsplit(validate_bitbucket_api_url(url)).path != urlsplit(source_url).path:
            raise BitbucketProviderReadError(kind="invalid_source")
        return self._parse_source_page(await self._read_json(session, url=url))

    async def read_repository_source_file(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        commit_hash: str,
        path: str,
        max_bytes: int,
    ) -> bytes:
        """Stream one raw commit-bound file and fail before its byte ceiling is crossed."""
        if max_bytes < 0:
            raise BitbucketProviderReadError(kind="limit_exceeded")
        url = repository_source_url(
            workspace=workspace,
            repository_slug=repository_slug,
            commit_hash=commit_hash,
            path=path,
        )
        return await self._read_bounded_bytes(
            session,
            url=url,
            max_bytes=max_bytes,
            expect_json=False,
        )

    @classmethod
    def _parse_branch_page(
        cls,
        page: Mapping[str, object],
    ) -> tuple[tuple[BitbucketBranch, ...], str | None]:
        values = page.get("values")
        if not isinstance(values, list):
            raise BitbucketProviderReadError()
        branches = tuple(cls._parse_branch(raw_branch) for raw_branch in values)
        raw_next = page.get("next")
        if raw_next is None:
            return branches, None
        if not isinstance(raw_next, str):
            raise BitbucketProviderReadError()
        try:
            return branches, validate_bitbucket_api_url(raw_next)
        except ValueError:
            raise BitbucketProviderReadError() from None

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

    @staticmethod
    def _parse_source_page(page: Mapping[str, object]) -> BitbucketSourcePage:
        values = page.get("values")
        if not isinstance(values, list):
            raise BitbucketProviderReadError(kind="invalid_source")
        entries: list[BitbucketSourceEntry] = []
        for raw_entry in values:
            if not isinstance(raw_entry, dict):
                raise BitbucketProviderReadError(kind="invalid_source")
            raw_path = raw_entry.get("path")
            raw_type = raw_entry.get("type")
            raw_size = raw_entry.get("size")
            if not isinstance(raw_path, str):
                raise BitbucketProviderReadError(kind="invalid_source")
            try:
                path = validate_repository_relative_path(raw_path)
            except ValueError:
                raise BitbucketProviderReadError(kind="invalid_source") from None
            if raw_type == "commit_directory":
                if raw_size is not None:
                    raise BitbucketProviderReadError(kind="invalid_source")
                entries.append(BitbucketSourceEntry(path=path, kind="directory", size=None))
            elif raw_type == "commit_file":
                if not isinstance(raw_size, int) or isinstance(raw_size, bool) or raw_size < 0:
                    raise BitbucketProviderReadError(kind="invalid_source")
                entries.append(BitbucketSourceEntry(path=path, kind="file", size=raw_size))
            else:
                raise BitbucketProviderReadError(kind="invalid_source")
        raw_next = page.get("next")
        if raw_next is None:
            next_url = None
        elif isinstance(raw_next, str):
            try:
                next_url = validate_bitbucket_api_url(raw_next)
            except ValueError:
                raise BitbucketProviderReadError(kind="invalid_source") from None
        else:
            raise BitbucketProviderReadError(kind="invalid_source")
        return BitbucketSourcePage(entries=tuple(entries), next_url=next_url)

    async def _read_json(self, session: Session, *, url: str) -> Mapping[str, object]:
        payload = await self._read_bounded_bytes(
            session,
            url=url,
            max_bytes=_MAX_JSON_RESPONSE_BYTES,
            expect_json=True,
        )
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError, UnicodeDecodeError:
            raise BitbucketProviderReadError(kind="invalid_source") from None
        if not isinstance(decoded, dict):
            raise BitbucketProviderReadError(kind="invalid_source")
        return cast(dict[str, object], decoded)

    async def _read_bounded_bytes(
        self,
        session: Session,
        *,
        url: str,
        max_bytes: int,
        expect_json: bool,
    ) -> bytes:
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
                    raise BitbucketProviderReadError(kind="invalid_source")
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
                content_encoding = response.headers.get("content-encoding")
                if content_encoding not in {None, "identity"}:
                    raise BitbucketProviderReadError(kind="invalid_source")
                if expect_json:
                    media_type = response.headers.get("content-type", "").split(";", 1)[0]
                    if media_type != "application/json":
                        raise BitbucketProviderReadError(kind="invalid_source")
                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        declared_length = int(content_length)
                    except ValueError:
                        raise BitbucketProviderReadError(kind="invalid_source") from None
                    if declared_length < 0:
                        raise BitbucketProviderReadError(kind="invalid_source")
                    if declared_length > max_bytes:
                        raise BitbucketProviderReadError(kind="limit_exceeded")
                chunks: list[bytes] = []
                byte_count = 0
                if response.is_stream_consumed:
                    chunks_to_count = (response.content,)
                    for chunk in chunks_to_count:
                        byte_count += len(chunk)
                        if byte_count > max_bytes:
                            raise BitbucketProviderReadError(kind="limit_exceeded")
                        chunks.append(chunk)
                else:
                    async for chunk in response.aiter_raw():
                        byte_count += len(chunk)
                        if byte_count > max_bytes:
                            raise BitbucketProviderReadError(kind="limit_exceeded")
                        chunks.append(chunk)
            self._credential_leases.require_current_repository_read_lease(session, lease)
            return b"".join(chunks)
        except BitbucketProviderReadError:
            raise
        except OAuthConnectionUnavailable:
            raise BitbucketProviderReadError(kind="disconnected") from None
        except OAuthGenerationRejected:
            raise BitbucketProviderReadError(kind="reauthorization_required") from None
        except httpx.DecodingError:
            raise BitbucketProviderReadError(kind="invalid_source") from None
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
    "BitbucketSourceEntry",
    "BitbucketSourcePage",
]
