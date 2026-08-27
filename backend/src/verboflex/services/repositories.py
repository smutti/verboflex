"""Registration authority for global reusable repository identity."""

from __future__ import annotations

import base64
import binascii
import json
import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, String, and_, func, literal, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from verboflex.models.repository import Repository

_PROVIDER_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_-]{0,99}")


class RepositoryConflict(ValueError):
    """Raised when a normalized provider identity is already registered."""


class RepositoryNotFound(LookupError):
    """Raised when an existing repository UUID cannot be selected."""


class InvalidRepositoryCursor(ValueError):
    """Raised when a collection cursor is malformed or noncanonical."""


DEFAULT_REPOSITORY_PAGE_SIZE = 50
MAX_REPOSITORY_PAGE_SIZE = 100
_CURSOR_VERSION = 1


@dataclass(frozen=True, slots=True)
class RepositoryRecord:
    """Closed credential-free projection of one global repository."""

    id: UUID
    workspace: str
    repository_slug: str
    descriptive_name: str | None


@dataclass(frozen=True, slots=True)
class RepositoryPage:
    """One stable keyset page of repository identities."""

    items: tuple[RepositoryRecord, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class _CursorPosition:
    sort_key: str
    workspace: str
    repository_slug: str
    repository_id: UUID


def _normalize_provider_identifier(raw_value: str) -> str:
    if not isinstance(raw_value, str):
        raise ValueError("invalid repository identity")
    normalized = raw_value.strip(" \t\n\r\f\v").lower()
    if _PROVIDER_IDENTIFIER.fullmatch(normalized) is None:
        raise ValueError("invalid repository identity")
    return normalized


def normalize_repository_identity(workspace: str, repository_slug: str) -> tuple[str, str]:
    """Return lowercase structural provider identity without provider I/O."""
    return (
        _normalize_provider_identifier(workspace),
        _normalize_provider_identifier(repository_slug),
    )


def _normalize_descriptive_name(raw_name: str | None) -> tuple[str | None, str | None]:
    if raw_name is None:
        return None, None
    if not isinstance(raw_name, str):
        raise ValueError("invalid repository description")
    display_name = " ".join(unicodedata.normalize("NFKC", raw_name).split())
    if not display_name or len(display_name) > 120:
        raise ValueError("invalid repository description")
    if "\x00" in display_name or not display_name.isprintable():
        raise ValueError("invalid repository description")
    return display_name, display_name.casefold()


def _record(repository: Repository) -> RepositoryRecord:
    return RepositoryRecord(
        id=repository.id,
        workspace=repository.workspace,
        repository_slug=repository.repository_slug,
        descriptive_name=repository.descriptive_name,
    )


def _repository_from_input(
    *,
    workspace: str,
    repository_slug: str,
    descriptive_name: str | None,
) -> Repository:
    """Validate transport-independent input before opening a write transaction."""
    normalized_workspace, normalized_slug = normalize_repository_identity(
        workspace,
        repository_slug,
    )
    normalized_name, descriptive_name_key = _normalize_descriptive_name(descriptive_name)
    return Repository(
        id=uuid4(),
        workspace=normalized_workspace,
        repository_slug=normalized_slug,
        descriptive_name=normalized_name,
        descriptive_name_key=descriptive_name_key,
    )


def register_repository(
    session: Session,
    *,
    workspace: str,
    repository_slug: str,
    descriptive_name: str | None = None,
) -> RepositoryRecord:
    """Create one repository or raise a bounded conflict for equal identity."""
    repository = _repository_from_input(
        workspace=workspace,
        repository_slug=repository_slug,
        descriptive_name=descriptive_name,
    )
    try:
        with session.begin():
            session.add(repository)
            session.flush()
    except IntegrityError as error:
        raise RepositoryConflict("repository unavailable") from error
    return _record(repository)


def get_repository(session: Session, *, repository_id: UUID) -> RepositoryRecord:
    """Select one existing UUID without creating or discovering provider state."""
    with session.begin():
        repository = session.scalar(select(Repository).where(Repository.id == repository_id))
        if repository is None:
            raise RepositoryNotFound("repository unavailable")
        return _record(repository)


def _repository_sort_key() -> ColumnElement[str]:
    fallback = Repository.workspace + literal("/") + Repository.repository_slug
    return func.coalesce(Repository.descriptive_name_key, fallback).cast(String).collate("C")


def _encode_cursor(position: _CursorPosition) -> str:
    payload = json.dumps(
        {
            "id": str(position.repository_id),
            "repository_slug": position.repository_slug,
            "sort_key": position.sort_key,
            "version": _CURSOR_VERSION,
            "workspace": position.workspace,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> _CursorPosition:
    if not cursor or len(cursor) > 1024:
        raise InvalidRepositoryCursor("invalid cursor")
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
            "id",
            "repository_slug",
            "sort_key",
            "version",
            "workspace",
        }:
            raise ValueError
        if (
            payload["version"] != _CURSOR_VERSION
            or not isinstance(payload["sort_key"], str)
            or not isinstance(payload["workspace"], str)
            or not isinstance(payload["repository_slug"], str)
        ):
            raise ValueError
        position = _CursorPosition(
            sort_key=payload["sort_key"],
            workspace=payload["workspace"],
            repository_slug=payload["repository_slug"],
            repository_id=UUID(payload["id"]),
        )
    except (
        binascii.Error,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ) as error:
        raise InvalidRepositoryCursor("invalid cursor") from error
    if _encode_cursor(position) != cursor:
        raise InvalidRepositoryCursor("invalid cursor")
    return position


def list_repositories(
    session: Session,
    *,
    limit: int = DEFAULT_REPOSITORY_PAGE_SIZE,
    cursor: str | None = None,
) -> RepositoryPage:
    """Return repository identities in stable descriptive/fallback order."""
    if not 1 <= limit <= MAX_REPOSITORY_PAGE_SIZE:
        raise ValueError("invalid page size")
    position = _decode_cursor(cursor) if cursor is not None else None
    sort_key = _repository_sort_key()
    with session.begin():
        statement = select(Repository)
        if position is not None:
            statement = statement.where(
                or_(
                    sort_key > position.sort_key,
                    and_(
                        sort_key == position.sort_key,
                        or_(
                            Repository.workspace > position.workspace,
                            and_(
                                Repository.workspace == position.workspace,
                                or_(
                                    Repository.repository_slug > position.repository_slug,
                                    and_(
                                        Repository.repository_slug == position.repository_slug,
                                        Repository.id > position.repository_id,
                                    ),
                                ),
                            ),
                        ),
                    ),
                )
            )
        repositories = list(
            session.scalars(
                statement.order_by(
                    sort_key,
                    Repository.workspace,
                    Repository.repository_slug,
                    Repository.id,
                ).limit(limit + 1)
            )
        )
        records = tuple(_record(repository) for repository in repositories[:limit])
        if len(repositories) > limit:
            last = repositories[limit - 1]
            next_cursor = _encode_cursor(
                _CursorPosition(
                    sort_key=(
                        last.descriptive_name_key
                        if last.descriptive_name_key is not None
                        else f"{last.workspace}/{last.repository_slug}"
                    ),
                    workspace=last.workspace,
                    repository_slug=last.repository_slug,
                    repository_id=last.id,
                )
            )
        else:
            next_cursor = None
    return RepositoryPage(items=records, next_cursor=next_cursor)
