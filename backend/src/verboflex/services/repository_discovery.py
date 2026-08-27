"""Read-only live repository discovery behind application-owned pagination."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from verboflex.integrations.bitbucket.client import BitbucketBranch
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


@dataclass(frozen=True, slots=True)
class BranchPage:
    items: tuple[BitbucketBranch, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class _BranchCursor:
    repository_id: UUID
    offset: int


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
