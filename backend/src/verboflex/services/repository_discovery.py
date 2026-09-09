"""Read-only live repository discovery behind application-owned pagination."""

from __future__ import annotations

import base64
import binascii
import json
from collections import deque
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from verboflex.integrations.bitbucket.client import (
    BitbucketAncestry,
    BitbucketBranch,
    BitbucketCommitDelta,
    BitbucketProviderReadError,
    BitbucketSourcePage,
)
from verboflex.integrations.bitbucket.urls import (
    validate_localization_root,
    validate_repository_relative_path,
)
from verboflex.services.repositories import RepositoryRecord, get_repository

DEFAULT_BRANCH_PAGE_SIZE = 50
MAX_BRANCH_PAGE_SIZE = 100
_CURSOR_VERSION = 1


class InvalidBranchCursor(ValueError):
    """Reject malformed, noncanonical, or repository-mismatched cursors."""


class BranchDiscoveryAdapter(Protocol):
    async def list_repository_branches(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
    ) -> tuple[BitbucketBranch, ...]: ...


class SourceDiscoveryAdapter(Protocol):
    async def compare_repository_ancestry(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        old_commit_hash: str,
        new_commit_hash: str,
    ) -> BitbucketAncestry: ...

    async def list_repository_diffstat(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        old_commit_hash: str,
        new_commit_hash: str,
        repository_side: Literal["direct", "keys", "translations"],
    ) -> BitbucketCommitDelta: ...

    async def resolve_repository_branch(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        branch: str,
    ) -> BitbucketBranch: ...

    async def list_repository_source_page(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        commit_hash: str,
        directory_path: str | None,
        next_url: str | None = None,
    ) -> BitbucketSourcePage: ...

    async def read_repository_source_file(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        commit_hash: str,
        path: str,
        max_bytes: int,
    ) -> bytes: ...


@dataclass(frozen=True, slots=True)
class BranchPage:
    items: tuple[BitbucketBranch, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class _BranchCursor:
    repository_id: UUID
    offset: int


@dataclass(frozen=True, slots=True)
class SourceDiscoveryBudget:
    max_pages: int
    max_entries: int
    max_depth: int
    max_candidate_files: int
    max_file_bytes: int
    max_total_bytes: int


SOURCE_DISCOVERY_BUDGET = SourceDiscoveryBudget(
    max_pages=50,
    max_entries=5_000,
    max_depth=12,
    max_candidate_files=500,
    max_file_bytes=1_048_576,
    max_total_bytes=20_971_520,
)
_CANDIDATE_SUFFIXES = (".xml", ".ts", ".json", ".strings", ".xlf", ".xliff")


@dataclass(frozen=True, slots=True)
class RepositorySourceFile:
    path: str
    content: bytes


@dataclass(frozen=True, slots=True)
class RepositorySourceSnapshot:
    commit_hash: str
    files: tuple[RepositorySourceFile, ...]
    total_bytes: int


def normalize_repository_relative_path(path: str) -> str:
    """Project one provider path into the repository-relative source namespace."""
    try:
        return validate_repository_relative_path(path)
    except ValueError:
        raise BitbucketProviderReadError(kind="invalid_source") from None


def _encode_cursor(position: _BranchCursor) -> str:
    payload = json.dumps(
        {
            "offset": position.offset,
            "repository_id": str(position.repository_id),
            "version": _CURSOR_VERSION,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str, *, repository_id: UUID) -> _BranchCursor:
    if not isinstance(cursor, str) or not cursor or len(cursor) > 1024:
        raise InvalidBranchCursor("invalid cursor")
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
            "offset",
            "repository_id",
            "version",
        }:
            raise ValueError
        position = _BranchCursor(
            repository_id=UUID(payload["repository_id"]),
            offset=payload["offset"],
        )
        if (
            payload["version"] != _CURSOR_VERSION
            or position.repository_id != repository_id
            or not isinstance(position.offset, int)
            or isinstance(position.offset, bool)
            or position.offset < 1
        ):
            raise ValueError
    except (
        binascii.Error,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ) as error:
        raise InvalidBranchCursor("invalid cursor") from error
    if _encode_cursor(position) != cursor:
        raise InvalidBranchCursor("invalid cursor")
    return position


async def list_live_repository_branches(
    session: Session,
    *,
    repository_id: UUID,
    adapter: BranchDiscoveryAdapter,
    limit: int = DEFAULT_BRANCH_PAGE_SIZE,
    cursor: str | None = None,
) -> BranchPage:
    """Resolve a registered repository, read live branches, and slice provider order."""
    if not 1 <= limit <= MAX_BRANCH_PAGE_SIZE:
        raise ValueError("invalid page size")
    offset = _decode_cursor(cursor, repository_id=repository_id).offset if cursor is not None else 0
    repository: RepositoryRecord = get_repository(session, repository_id=repository_id)
    branches = await adapter.list_repository_branches(
        session,
        workspace=repository.workspace,
        repository_slug=repository.repository_slug,
    )
    items = branches[offset : offset + limit]
    next_offset = offset + len(items)
    next_cursor = (
        _encode_cursor(_BranchCursor(repository_id=repository_id, offset=next_offset))
        if next_offset < len(branches)
        else None
    )
    return BranchPage(items=items, next_cursor=next_cursor)


async def resolve_configured_repository_branch(
    session: Session,
    *,
    repository_id: UUID,
    branch_name: str,
    adapter: SourceDiscoveryAdapter,
) -> BitbucketBranch:
    """Resolve one registered repository branch through the exact safe-adapter read."""
    repository = get_repository(session, repository_id=repository_id)
    resolved = await adapter.resolve_repository_branch(
        session,
        workspace=repository.workspace,
        repository_slug=repository.repository_slug,
        branch=branch_name,
    )
    if resolved.name != branch_name:
        raise BitbucketProviderReadError(kind="invalid_source")
    return resolved


async def discover_repository_sources_for_record(
    session: Session,
    *,
    repository: RepositoryRecord,
    branch: str,
    adapter: SourceDiscoveryAdapter,
    localization_root: str | None = None,
) -> RepositorySourceSnapshot:
    """Resolve one branch and read every candidate under the immutable A-03 budget."""
    root = (
        validate_localization_root(localization_root)
        if localization_root is not None
        else None
    )
    resolved = await adapter.resolve_repository_branch(
        session,
        workspace=repository.workspace,
        repository_slug=repository.repository_slug,
        branch=branch,
    )
    if resolved.name != branch:
        raise BitbucketProviderReadError(kind="invalid_source")

    pages = 0
    entry_count = 0
    seen_paths: set[str] = set()
    candidate_entries: list[tuple[str, int]] = []
    directories: deque[str | None] = deque([root])
    while directories:
        directory_path = directories.popleft()
        next_url: str | None = None
        while True:
            if pages >= SOURCE_DISCOVERY_BUDGET.max_pages:
                raise BitbucketProviderReadError(kind="limit_exceeded")
            page = await adapter.list_repository_source_page(
                session,
                workspace=repository.workspace,
                repository_slug=repository.repository_slug,
                commit_hash=resolved.commit_hash,
                directory_path=directory_path,
                next_url=next_url,
            )
            pages += 1
            for entry in page.entries:
                path = normalize_repository_relative_path(entry.path)
                if root is not None and not path.startswith(root + "/"):
                    raise BitbucketProviderReadError(kind="invalid_source")
                if path in seen_paths:
                    raise BitbucketProviderReadError(kind="invalid_source")
                seen_paths.add(path)
                entry_count += 1
                if entry_count > SOURCE_DISCOVERY_BUDGET.max_entries:
                    raise BitbucketProviderReadError(kind="limit_exceeded")
                if len(path.split("/")) > SOURCE_DISCOVERY_BUDGET.max_depth:
                    raise BitbucketProviderReadError(kind="limit_exceeded")
                if entry.kind == "directory":
                    directories.append(path)
                    continue
                if entry.size is None:
                    raise BitbucketProviderReadError(kind="invalid_source")
                if path.casefold().endswith(_CANDIDATE_SUFFIXES):
                    if entry.size > SOURCE_DISCOVERY_BUDGET.max_file_bytes:
                        raise BitbucketProviderReadError(kind="limit_exceeded")
                    candidate_entries.append((path, entry.size))
                    if len(candidate_entries) > SOURCE_DISCOVERY_BUDGET.max_candidate_files:
                        raise BitbucketProviderReadError(kind="limit_exceeded")
            if page.next_url is None:
                break
            next_url = page.next_url

    files: list[RepositorySourceFile] = []
    total_bytes = 0
    for path, declared_size in sorted(candidate_entries):
        remaining = SOURCE_DISCOVERY_BUDGET.max_total_bytes - total_bytes
        if declared_size > remaining or remaining <= 0:
            raise BitbucketProviderReadError(kind="limit_exceeded")
        content = await adapter.read_repository_source_file(
            session,
            workspace=repository.workspace,
            repository_slug=repository.repository_slug,
            commit_hash=resolved.commit_hash,
            path=path,
            max_bytes=min(SOURCE_DISCOVERY_BUDGET.max_file_bytes, remaining),
        )
        total_bytes += len(content)
        if (
            len(content) > SOURCE_DISCOVERY_BUDGET.max_file_bytes
            or total_bytes > SOURCE_DISCOVERY_BUDGET.max_total_bytes
        ):
            raise BitbucketProviderReadError(kind="limit_exceeded")
        files.append(RepositorySourceFile(path=path, content=content))

    return RepositorySourceSnapshot(
        commit_hash=resolved.commit_hash,
        files=tuple(files),
        total_bytes=total_bytes,
    )


async def discover_live_repository_sources(
    session: Session,
    *,
    repository_id: UUID,
    branch: str,
    adapter: SourceDiscoveryAdapter,
    localization_root: str | None = None,
) -> RepositorySourceSnapshot:
    """Resolve one registered repository before any commit-bound provider read."""
    repository = get_repository(session, repository_id=repository_id)
    return await discover_repository_sources_for_record(
        session,
        repository=repository,
        branch=branch,
        adapter=adapter,
        localization_root=localization_root,
    )
