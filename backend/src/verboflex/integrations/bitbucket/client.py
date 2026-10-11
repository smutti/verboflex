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
    PHASE_3_READ_OPERATIONS,
    PHASE_8_WRITE_OPERATIONS,
    BitbucketOperation,
    repository_branch_url,
    repository_branches_url,
    repository_commit_ancestry_url,
    repository_diffstat_url,
    repository_metadata_url,
    repository_source_metadata_url,
    repository_source_url,
    validate_bitbucket_api_url,
    validate_provider_commit_hash,
    validate_repository_relative_path,
    workspace_repositories_url,
)
from verboflex.services.bitbucket_oauth import (
    PULLREQUEST_WRITE_IMPLICATION_CLOSURE,
    PULLREQUEST_WRITE_SCOPE,
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
    "rate_limited",
    "unavailable",
    "timeout",
    "invalid_source",
    "limit_exceeded",
]

_PROVIDER_FAILURE_KINDS = frozenset(
    {
        "disconnected",
        "reauthorization_required",
        "permission_denied",
        "not_found",
        "rate_limited",
        "unavailable",
        "timeout",
        "invalid_source",
        "limit_exceeded",
    }
)

_MAX_JSON_RESPONSE_BYTES = 1_048_576
MAX_ANCESTRY_PAGES = 50
MAX_ANCESTRY_COMMITS = 5_000
MAX_DIFFSTAT_PAGES = 50
MAX_DIFFSTAT_ROWS = 5_000
MAX_DIFFSTAT_PATH_LENGTH = 4_096
MAX_DIFFSTAT_PATH_BYTES = 1_048_576

RepositorySide = Literal["direct", "keys", "translations"]
AncestryRelation = Literal["equal", "descendant", "diverged"]
FileDeltaChange = Literal["added", "modified", "removed"]


class BitbucketProviderReadError(RuntimeError):
    """Bound every provider, credential, and response failure to one safe message."""

    def __init__(
        self,
        *,
        kind: ProviderFailureKind = "unavailable",
        provider_status: int | None = None,
        operation: BitbucketOperation | None = None,
    ) -> None:
        super().__init__(PROVIDER_READ_FAILED_MESSAGE)
        self.kind: ProviderFailureKind = kind if kind in _PROVIDER_FAILURE_KINDS else "unavailable"
        self.provider_status = (
            provider_status
            if isinstance(provider_status, int)
            and not isinstance(provider_status, bool)
            and 100 <= provider_status <= 599
            else None
        )
        if operation is not None and (
            not isinstance(operation, BitbucketOperation)
            or operation not in PHASE_3_READ_OPERATIONS
        ):
            raise ValueError("Bitbucket provider operation rejected")
        self.operation = operation


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
    attributes: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class BitbucketSourceMetadata:
    """Explicit provider evidence; absent attributes never imply a regular file."""

    path: str
    commit_hash: str
    size_bytes: int
    attributes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BitbucketSourcePage:
    """One source-tree page and its validated opaque continuation URL."""

    entries: tuple[BitbucketSourceEntry, ...]
    next_url: str | None


@dataclass(frozen=True)
class BitbucketAncestry:
    """Complete bounded reachability result for two immutable commits."""

    old_commit_hash: str
    new_commit_hash: str
    relation: AncestryRelation
    complete: bool


@dataclass(frozen=True)
class BitbucketFileDelta:
    """One metadata-only localization-file change in provider traversal order."""

    repository_side: RepositorySide
    ordinal: int
    change: FileDeltaChange
    path: str


@dataclass(frozen=True)
class BitbucketCommitDelta:
    """One complete bounded diffstat between exact source commits."""

    old_commit_hash: str
    new_commit_hash: str
    files: tuple[BitbucketFileDelta, ...]
    complete: bool


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

    async def list_workspace_repositories(
        self,
        session: Session,
        *,
        workspace: str,
        query: str = "",
        limit: int = 20,
        next_url: str | None = None,
    ) -> Mapping[str, object]:
        """Read exactly one bounded provider page, never another workspace or host."""
        first_url = workspace_repositories_url(workspace=workspace, query=query, limit=limit)
        url = next_url or first_url
        operation = BitbucketOperation.WORKSPACE_REPOSITORIES
        try:
            validate_bitbucket_api_url(url, operation=operation)
            if urlsplit(url).path.rstrip("/") != urlsplit(first_url).path:
                raise ValueError
        except ValueError:
            raise BitbucketProviderReadError(kind="invalid_source", operation=operation) from None
        page = await self._read_json(session, operation=operation, url=url)
        values = page.get("values")
        if not isinstance(values, list) or len(values) > limit:
            raise BitbucketProviderReadError(kind="invalid_source", operation=operation)
        next_page = self._parse_pagination_next(page, operation=operation)
        if next_page is not None and (
            urlsplit(next_page).path.rstrip("/") != urlsplit(first_url).path or next_page == url
        ):
            raise BitbucketProviderReadError(kind="invalid_source", operation=operation)
        return page

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
        return await self._read_json(
            session,
            operation=BitbucketOperation.REPOSITORY_METADATA,
            url=url,
        )

    async def list_repository_branches(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
    ) -> tuple[BitbucketBranch, ...]:
        """Traverse opaque provider pages in order and preserve exact branch names."""
        first_url = repository_branches_url(
            workspace=workspace,
            repository_slug=repository_slug,
        )
        expected_path = urlsplit(first_url).path
        next_url: str | None = first_url
        branches: list[BitbucketBranch] = []
        visited: set[str] = set()
        while next_url is not None:
            if next_url in visited or len(visited) >= 50:
                raise BitbucketProviderReadError(operation=BitbucketOperation.BRANCH_LIST)
            visited.add(next_url)
            page = await self._read_json(
                session,
                operation=BitbucketOperation.BRANCH_LIST,
                url=next_url,
            )
            page_branches, next_url = self._parse_branch_page(page)
            if next_url is not None and urlsplit(next_url).path != expected_path:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.BRANCH_LIST,
                )
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
        resolved = self._parse_branch(
            await self._read_json(
                session,
                operation=BitbucketOperation.BRANCH_RESOLVE,
                url=url,
            ),
            operation=BitbucketOperation.BRANCH_RESOLVE,
        )
        if resolved.name != branch:
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=BitbucketOperation.BRANCH_RESOLVE,
            )
        return resolved

    async def compare_repository_ancestry(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        old_commit_hash: str,
        new_commit_hash: str,
    ) -> BitbucketAncestry:
        """Prove equality or bounded reachability from the proposed commit."""
        previous = validate_provider_commit_hash(old_commit_hash)
        proposed = validate_provider_commit_hash(new_commit_hash)
        if previous == proposed:
            return BitbucketAncestry(
                old_commit_hash=previous,
                new_commit_hash=proposed,
                relation="equal",
                complete=True,
            )

        first_url = repository_commit_ancestry_url(
            workspace=workspace,
            repository_slug=repository_slug,
            old_commit_hash=previous,
            new_commit_hash=proposed,
        )
        expected_path = urlsplit(first_url).path
        next_url: str | None = first_url
        visited_urls: set[str] = set()
        visited_commits: set[str] = set()
        first_commit = True
        while next_url is not None:
            if next_url in visited_urls:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.COMMIT_ANCESTRY,
                )
            if len(visited_urls) >= MAX_ANCESTRY_PAGES:
                raise BitbucketProviderReadError(
                    kind="limit_exceeded",
                    operation=BitbucketOperation.COMMIT_ANCESTRY,
                )
            visited_urls.add(next_url)
            page = await self._read_json(
                session,
                operation=BitbucketOperation.COMMIT_ANCESTRY,
                url=next_url,
            )
            commit_hashes, next_url = self._parse_commit_page(page)
            if not commit_hashes:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.COMMIT_ANCESTRY,
                )
            if first_commit and commit_hashes[0] != proposed:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.COMMIT_ANCESTRY,
                )
            first_commit = False
            for commit_hash in commit_hashes:
                if commit_hash in visited_commits:
                    raise BitbucketProviderReadError(
                        kind="invalid_source",
                        operation=BitbucketOperation.COMMIT_ANCESTRY,
                    )
                visited_commits.add(commit_hash)
                if len(visited_commits) > MAX_ANCESTRY_COMMITS:
                    raise BitbucketProviderReadError(
                        kind="limit_exceeded",
                        operation=BitbucketOperation.COMMIT_ANCESTRY,
                    )
                if commit_hash == previous:
                    return BitbucketAncestry(
                        old_commit_hash=previous,
                        new_commit_hash=proposed,
                        relation="descendant",
                        complete=True,
                    )
            if next_url is not None and urlsplit(next_url).path != expected_path:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.COMMIT_ANCESTRY,
                )
        return BitbucketAncestry(
            old_commit_hash=previous,
            new_commit_hash=proposed,
            relation="diverged",
            complete=True,
        )

    async def list_repository_diffstat(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        old_commit_hash: str,
        new_commit_hash: str,
        repository_side: RepositorySide,
    ) -> BitbucketCommitDelta:
        """Return every bounded localization-file change without provider payloads."""
        if repository_side not in {"direct", "keys", "translations"}:
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=BitbucketOperation.COMMIT_DIFFSTAT,
            )
        previous = validate_provider_commit_hash(old_commit_hash)
        proposed = validate_provider_commit_hash(new_commit_hash)
        first_url = repository_diffstat_url(
            workspace=workspace,
            repository_slug=repository_slug,
            old_commit_hash=previous,
            new_commit_hash=proposed,
        )
        expected_path = urlsplit(first_url).path
        next_url: str | None = first_url
        visited_urls: set[str] = set()
        seen_paths: set[str] = set()
        files: list[BitbucketFileDelta] = []
        row_count = 0
        path_bytes = 0
        while next_url is not None:
            if next_url in visited_urls:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.COMMIT_DIFFSTAT,
                )
            if len(visited_urls) >= MAX_DIFFSTAT_PAGES:
                raise BitbucketProviderReadError(
                    kind="limit_exceeded",
                    operation=BitbucketOperation.COMMIT_DIFFSTAT,
                )
            visited_urls.add(next_url)
            page = await self._read_json(
                session,
                operation=BitbucketOperation.COMMIT_DIFFSTAT,
                url=next_url,
            )
            rows, next_url = self._parse_diffstat_page(page)
            row_count += len(rows)
            if row_count > MAX_DIFFSTAT_ROWS:
                raise BitbucketProviderReadError(
                    kind="limit_exceeded",
                    operation=BitbucketOperation.COMMIT_DIFFSTAT,
                )
            for change, path in rows:
                path_bytes += len(path.encode("utf-8"))
                if len(path) > MAX_DIFFSTAT_PATH_LENGTH or path_bytes > MAX_DIFFSTAT_PATH_BYTES:
                    raise BitbucketProviderReadError(
                        kind="limit_exceeded",
                        operation=BitbucketOperation.COMMIT_DIFFSTAT,
                    )
                if not path.casefold().endswith((".xml", ".ts", ".json", ".strings")):
                    continue
                if path in seen_paths:
                    raise BitbucketProviderReadError(
                        kind="invalid_source",
                        operation=BitbucketOperation.COMMIT_DIFFSTAT,
                    )
                seen_paths.add(path)
                files.append(
                    BitbucketFileDelta(
                        repository_side=repository_side,
                        ordinal=len(files),
                        change=change,
                        path=path,
                    )
                )
            if next_url is not None and urlsplit(next_url).path != expected_path:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.COMMIT_DIFFSTAT,
                )
        return BitbucketCommitDelta(
            old_commit_hash=previous,
            new_commit_hash=proposed,
            files=tuple(files),
            complete=True,
        )

    async def list_repository_source_page(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        commit_hash: str,
        directory_path: str | None,
        next_url: str | None = None,
        max_depth: int | None = None,
    ) -> BitbucketSourcePage:
        """Read one commit-bound source page through a validated continuation."""
        source_url = repository_source_url(
            workspace=workspace,
            repository_slug=repository_slug,
            commit_hash=commit_hash,
            path=directory_path,
            paginated=True,
            max_depth=max_depth,
        )
        url = next_url or source_url
        if (
            urlsplit(validate_bitbucket_api_url(url, operation=BitbucketOperation.SOURCE_TREE)).path
            != urlsplit(source_url).path
        ):
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=BitbucketOperation.SOURCE_TREE,
            )
        return self._parse_source_page(
            await self._read_json(
                session,
                operation=BitbucketOperation.SOURCE_TREE,
                url=url,
            )
        )

    async def read_repository_source_metadata(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        commit_hash: str,
        path: str,
    ) -> BitbucketSourceMetadata:
        """Read bounded metadata for one exact file; never follow provider links."""
        operation = BitbucketOperation.SOURCE_METADATA
        url = repository_source_metadata_url(
            workspace=workspace, repository_slug=repository_slug, commit_hash=commit_hash, path=path
        )
        payload = await self._read_json(session, operation=operation, url=url)
        commit = payload.get("commit")
        size = payload.get("size")
        attributes = payload.get("attributes")
        if (
            payload.get("type") != "commit_file"
            or payload.get("path") != path
            or not isinstance(commit, dict)
            or commit.get("hash") != commit_hash
            or type(size) is not int
            or size < 0
            or not isinstance(attributes, list)
            or len(attributes) > 4
            or any(type(item) is not str for item in attributes)
        ):
            raise BitbucketProviderReadError(kind="invalid_source", operation=operation)
        if len(set(attributes)) != len(attributes) or not set(attributes).issubset(
            {"binary", "executable", "link", "subrepository"}
        ):
            raise BitbucketProviderReadError(kind="invalid_source", operation=operation)
        return BitbucketSourceMetadata(path, commit_hash, size, tuple(sorted(attributes)))

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
            raise BitbucketProviderReadError(
                kind="limit_exceeded",
                operation=BitbucketOperation.SOURCE_FILE,
            )
        url = repository_source_url(
            workspace=workspace,
            repository_slug=repository_slug,
            commit_hash=commit_hash,
            path=path,
        )
        return await self._read_bounded_bytes(
            session,
            operation=BitbucketOperation.SOURCE_FILE,
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
            raise BitbucketProviderReadError(operation=BitbucketOperation.BRANCH_LIST)
        branches = tuple(
            cls._parse_branch(raw_branch, operation=BitbucketOperation.BRANCH_LIST)
            for raw_branch in values
        )
        raw_next = page.get("next")
        if raw_next is None:
            return branches, None
        if not isinstance(raw_next, str):
            raise BitbucketProviderReadError(operation=BitbucketOperation.BRANCH_LIST)
        try:
            return branches, validate_bitbucket_api_url(
                raw_next,
                operation=BitbucketOperation.BRANCH_LIST,
            )
        except ValueError:
            raise BitbucketProviderReadError(operation=BitbucketOperation.BRANCH_LIST) from None

    @staticmethod
    def _parse_pagination_next(
        page: Mapping[str, object],
        *,
        operation: BitbucketOperation,
    ) -> str | None:
        raw_next = page.get("next")
        if raw_next is None:
            return None
        if not isinstance(raw_next, str):
            raise BitbucketProviderReadError(kind="invalid_source", operation=operation)
        try:
            return validate_bitbucket_api_url(raw_next, operation=operation)
        except ValueError:
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=operation,
            ) from None

    @classmethod
    def _parse_commit_page(
        cls,
        page: Mapping[str, object],
    ) -> tuple[tuple[str, ...], str | None]:
        values = page.get("values")
        if not isinstance(values, list):
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=BitbucketOperation.COMMIT_ANCESTRY,
            )
        commits: list[str] = []
        for value in values:
            commit_hash = value.get("hash") if isinstance(value, dict) else None
            if not isinstance(commit_hash, str):
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.COMMIT_ANCESTRY,
                )
            try:
                commits.append(validate_provider_commit_hash(commit_hash))
            except ValueError:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.COMMIT_ANCESTRY,
                ) from None
        return tuple(commits), cls._parse_pagination_next(
            page,
            operation=BitbucketOperation.COMMIT_ANCESTRY,
        )

    @classmethod
    def _parse_diffstat_page(
        cls,
        page: Mapping[str, object],
    ) -> tuple[tuple[tuple[FileDeltaChange, str], ...], str | None]:
        values = page.get("values")
        if not isinstance(values, list):
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=BitbucketOperation.COMMIT_DIFFSTAT,
            )
        rows: list[tuple[FileDeltaChange, str]] = []
        for value in values:
            if not isinstance(value, dict):
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.COMMIT_DIFFSTAT,
                )
            raw_status = value.get("status")
            old_entry = value.get("old")
            new_entry = value.get("new")
            old_path = cls._diffstat_file_path(old_entry)
            new_path = cls._diffstat_file_path(new_entry)
            if raw_status == "added" and new_path is not None:
                change: FileDeltaChange = "added"
                path = new_path
            elif raw_status == "removed" and old_path is not None:
                change = "removed"
                path = old_path
            elif (
                raw_status == "modified"
                and old_path is not None
                and new_path is not None
                and old_path == new_path
            ):
                change = "modified"
                path = new_path
            else:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.COMMIT_DIFFSTAT,
                )
            rows.append((change, path))
        return tuple(rows), cls._parse_pagination_next(
            page,
            operation=BitbucketOperation.COMMIT_DIFFSTAT,
        )

    @staticmethod
    def _diffstat_file_path(raw_entry: object) -> str | None:
        if raw_entry is None:
            return None
        if not isinstance(raw_entry, dict) or raw_entry.get("type") != "commit_file":
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=BitbucketOperation.COMMIT_DIFFSTAT,
            )
        raw_path = raw_entry.get("path")
        if not isinstance(raw_path, str):
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=BitbucketOperation.COMMIT_DIFFSTAT,
            )
        try:
            return validate_repository_relative_path(raw_path)
        except ValueError:
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=BitbucketOperation.COMMIT_DIFFSTAT,
            ) from None

    @staticmethod
    def _parse_branch(
        raw_branch: object,
        *,
        operation: BitbucketOperation | None = None,
    ) -> BitbucketBranch:
        if not isinstance(raw_branch, dict):
            raise BitbucketProviderReadError(operation=operation)
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
            raise BitbucketProviderReadError(operation=operation)
        return BitbucketBranch(name=name, commit_hash=commit_hash)

    @staticmethod
    def _parse_source_page(page: Mapping[str, object]) -> BitbucketSourcePage:
        values = page.get("values")
        if not isinstance(values, list):
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=BitbucketOperation.SOURCE_TREE,
            )
        entries: list[BitbucketSourceEntry] = []
        for raw_entry in values:
            if not isinstance(raw_entry, dict):
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.SOURCE_TREE,
                )
            raw_path = raw_entry.get("path")
            raw_type = raw_entry.get("type")
            raw_size = raw_entry.get("size")
            if not isinstance(raw_path, str):
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.SOURCE_TREE,
                )
            try:
                path = validate_repository_relative_path(raw_path)
            except ValueError:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.SOURCE_TREE,
                ) from None
            if raw_type == "commit_directory":
                if raw_size is not None:
                    raise BitbucketProviderReadError(
                        kind="invalid_source",
                        operation=BitbucketOperation.SOURCE_TREE,
                    )
                entries.append(BitbucketSourceEntry(path=path, kind="directory", size=None))
            elif raw_type == "commit_file":
                if not isinstance(raw_size, int) or isinstance(raw_size, bool) or raw_size < 0:
                    raise BitbucketProviderReadError(
                        kind="invalid_source",
                        operation=BitbucketOperation.SOURCE_TREE,
                    )
                entries.append(BitbucketSourceEntry(path=path, kind="file", size=raw_size))
            else:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.SOURCE_TREE,
                )
        raw_next = page.get("next")
        if raw_next is None:
            next_url = None
        elif isinstance(raw_next, str):
            try:
                next_url = validate_bitbucket_api_url(
                    raw_next,
                    operation=BitbucketOperation.SOURCE_TREE,
                )
            except ValueError:
                raise BitbucketProviderReadError(
                    kind="invalid_source",
                    operation=BitbucketOperation.SOURCE_TREE,
                ) from None
        else:
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=BitbucketOperation.SOURCE_TREE,
            )
        return BitbucketSourcePage(entries=tuple(entries), next_url=next_url)

    async def _read_json(
        self,
        session: Session,
        *,
        operation: BitbucketOperation,
        url: str,
    ) -> Mapping[str, object]:
        payload = await self._read_bounded_bytes(
            session,
            operation=operation,
            url=url,
            max_bytes=_MAX_JSON_RESPONSE_BYTES,
            expect_json=True,
        )
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError, UnicodeDecodeError:
            decoded = None
        if not isinstance(decoded, dict):
            raise BitbucketProviderReadError(
                kind="invalid_source",
                operation=operation,
            )
        return cast(dict[str, object], decoded)

    async def _read_bounded_bytes(
        self,
        session: Session,
        *,
        operation: BitbucketOperation,
        url: str,
        max_bytes: int,
        expect_json: bool,
    ) -> bytes:
        validated_url = validate_bitbucket_api_url(url, operation=operation)
        failure_kind: ProviderFailureKind | None = None
        try:
            lease = self._credential_leases.acquire_repository_read_lease(session)
            self._credential_leases.require_current_repository_read_lease(session, lease)
            async with self._client.stream(
                "GET",
                validated_url,
                headers={"Authorization": f"Bearer {lease.access_token}"},
            ) as response:
                if response.is_redirect:
                    raise BitbucketProviderReadError(
                        kind="invalid_source",
                        provider_status=response.status_code,
                    )
                if not 200 <= response.status_code < 300:
                    kind: ProviderFailureKind
                    if response.status_code == 401:
                        kind = "reauthorization_required"
                    elif response.status_code == 403:
                        kind = "permission_denied"
                    elif response.status_code == 404:
                        kind = "not_found"
                    elif response.status_code == 429:
                        kind = "rate_limited"
                    elif response.status_code in {408, 504}:
                        kind = "timeout"
                    else:
                        kind = "unavailable"
                    raise BitbucketProviderReadError(
                        kind=kind,
                        provider_status=response.status_code,
                    )
                raw_scopes = response.headers.get("x-oauth-scopes")
                scopes = raw_scopes.replace(",", " ").split() if isinstance(raw_scopes, str) else []
                scope_set = frozenset(scopes)
                if (
                    PULLREQUEST_WRITE_SCOPE not in scope_set
                    or not scope_set.issubset(PULLREQUEST_WRITE_IMPLICATION_CLOSURE)
                    or len(scope_set) != len(scopes)
                ):
                    raise BitbucketProviderReadError(
                        kind="permission_denied",
                        provider_status=response.status_code,
                    )
                content_encoding = response.headers.get("content-encoding")
                if content_encoding not in {None, "identity"}:
                    raise BitbucketProviderReadError(
                        kind="invalid_source",
                        provider_status=response.status_code,
                    )
                if expect_json:
                    media_type = response.headers.get("content-type", "").split(";", 1)[0]
                    if media_type != "application/json":
                        raise BitbucketProviderReadError(
                            kind="invalid_source",
                            provider_status=response.status_code,
                        )
                content_length = response.headers.get("content-length")
                if content_length is not None:
                    if not content_length.isascii() or not content_length.isdecimal():
                        raise BitbucketProviderReadError(
                            kind="invalid_source",
                            provider_status=response.status_code,
                        )
                    declared_length = int(content_length)
                    if declared_length > max_bytes:
                        raise BitbucketProviderReadError(
                            kind="limit_exceeded",
                            provider_status=response.status_code,
                        )
                chunks: list[bytes] = []
                byte_count = 0
                if response.is_stream_consumed:
                    byte_count = self._append_bounded_chunk(
                        chunks,
                        byte_count=byte_count,
                        chunk=response.content,
                        max_bytes=max_bytes,
                        provider_status=response.status_code,
                    )
                else:
                    async for chunk in response.aiter_raw():
                        byte_count = self._append_bounded_chunk(
                            chunks,
                            byte_count=byte_count,
                            chunk=chunk,
                            max_bytes=max_bytes,
                            provider_status=response.status_code,
                        )
            self._credential_leases.require_current_repository_read_lease(session, lease)
            return b"".join(chunks)
        except BitbucketProviderReadError as error:
            if error.operation is None:
                error.operation = operation
            raise
        except OAuthConnectionUnavailable:
            failure_kind = "disconnected"
        except OAuthGenerationRejected:
            failure_kind = "reauthorization_required"
        except httpx.DecodingError:
            failure_kind = "invalid_source"
        except httpx.TimeoutException:
            failure_kind = "timeout"
        except Exception:
            failure_kind = "unavailable"
        raise BitbucketProviderReadError(
            kind=failure_kind or "unavailable",
            operation=operation,
        )

    @staticmethod
    def _append_bounded_chunk(
        chunks: list[bytes],
        *,
        byte_count: int,
        chunk: bytes,
        max_bytes: int,
        provider_status: int | None = None,
    ) -> int:
        """Count each transport byte exactly once before retaining it in memory."""
        next_count = byte_count + len(chunk)
        if next_count > max_bytes:
            raise BitbucketProviderReadError(
                kind="limit_exceeded",
                provider_status=provider_status,
            )
        chunks.append(chunk)
        return next_count

    async def aclose(self) -> None:
        """Close the one process-scoped connection pool explicitly."""
        await self._client.aclose()


__all__ = [
    "PHASE_3_READ_OPERATIONS",
    "PHASE_8_WRITE_OPERATIONS",
    "BitbucketCredentialLease",
    "BitbucketBranch",
    "BitbucketAncestry",
    "BitbucketCommitDelta",
    "BitbucketFileDelta",
    "BitbucketHttpAdapter",
    "BitbucketOperation",
    "BitbucketProviderReadError",
    "BitbucketSourceEntry",
    "BitbucketSourceMetadata",
    "BitbucketSourcePage",
]
