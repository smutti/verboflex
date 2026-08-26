"""Registration authority for global reusable repository identity."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from verboflex.models.repository import Repository

_PROVIDER_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_-]{0,99}")


class RepositoryConflict(ValueError):
    """Raised when a normalized provider identity is already registered."""


class RepositoryNotFound(LookupError):
    """Raised when an existing repository UUID cannot be selected."""


@dataclass(frozen=True, slots=True)
class RepositoryRecord:
    """Closed credential-free projection of one global repository."""

    id: UUID
    workspace: str
    repository_slug: str
    descriptive_name: str | None


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
