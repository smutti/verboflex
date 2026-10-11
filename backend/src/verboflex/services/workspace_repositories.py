"""Workspace-scoped provider search and idempotent local repository selection."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from verboflex.audit.ledger import BITBUCKET_AUDIT_ENTITY, record_audit
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter, BitbucketProviderReadError
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.repository import Repository
from verboflex.schemas.admin_workspace import (
    AdminBitbucketRepositoryListResponse,
    AdminBitbucketRepositoryResponse,
)
from verboflex.services.repositories import (
    RepositoryRecord,
    _normalize_descriptive_name,
    _record,
    normalize_repository_identity,
)
from verboflex.services.signed_cursor import InvalidSignedCursor, SignedCursorCodec


class WorkspaceRequired(ValueError):
    """An administrator must configure a workspace before discovery."""


class WorkspaceChanged(ValueError):
    """The selected workspace changed while a picker request was in flight."""


def get_workspace(session: Session) -> str | None:
    with session.begin():
        return session.scalar(
            select(BitbucketConnection.workspace).where(BitbucketConnection.id == 1)
        )


def set_workspace(session: Session, workspace: str, *, actor_id: UUID | None) -> str:
    workspace = normalize_repository_identity(workspace, "repository")[0]
    with session.begin():
        changed = session.scalar(
            insert(BitbucketConnection)
            .values(id=1, workspace=workspace)
            .on_conflict_do_update(
                index_elements=[BitbucketConnection.id],
                set_={"workspace": workspace},
                where=BitbucketConnection.workspace.is_distinct_from(workspace),
            )
            .returning(BitbucketConnection.id)
        )
        if changed is not None:
            record_audit(
                session,
                actor_id=actor_id,
                action="workspace.updated",
                entity_id=BITBUCKET_AUDIT_ENTITY,
            )
    return workspace


def _configured_workspace(session: Session) -> str:
    workspace = get_workspace(session)
    if workspace is None:
        raise WorkspaceRequired
    return workspace


def _provider_repository(value: object, workspace: str) -> AdminBitbucketRepositoryResponse:
    if not isinstance(value, dict):
        raise BitbucketProviderReadError(kind="invalid_source")
    slug, name = value.get("slug"), value.get("name")
    provider_workspace = value.get("workspace")
    try:
        if (
            not isinstance(slug, str)
            or not isinstance(name, str)
            or not name.strip()
            or len(name) > 255
            or not name.isprintable()
            or not isinstance(provider_workspace, dict)
            or provider_workspace.get("slug") != workspace
        ):
            raise ValueError
        normalized_workspace, normalized_slug = normalize_repository_identity(workspace, slug)
        if slug != normalized_slug:
            raise ValueError
    except ValueError:
        raise BitbucketProviderReadError(kind="invalid_source") from None
    return AdminBitbucketRepositoryResponse(
        workspace=normalized_workspace,
        repository_slug=normalized_slug,
        name=name,
    )


async def list_workspace_repositories(
    session: Session,
    *,
    adapter: BitbucketHttpAdapter,
    principal_id: UUID,
    secret: str,
    query: str = "",
    limit: int = 20,
    cursor: str | None = None,
) -> AdminBitbucketRepositoryListResponse:
    workspace = _configured_workspace(session)
    query = query.strip()
    binding = {
        "kind": "workspace-repositories",
        "workspace": workspace,
        "query": query,
        "limit": limit,
        "principal": str(principal_id),
    }
    codec = SignedCursorCodec(secret)
    next_url = None
    if cursor is not None:
        payload = codec.decode_payload(cursor, required_keys=frozenset((*binding, "next")))
        if any(payload.get(key) != value for key, value in binding.items()) or not isinstance(
            payload["next"], str
        ):
            raise InvalidSignedCursor("Invalid cursor")
        next_url = payload["next"]
    page = await adapter.list_workspace_repositories(
        session,
        workspace=workspace,
        query=query,
        limit=limit,
        next_url=next_url,
    )
    values = page["values"]
    if not isinstance(values, list):
        raise BitbucketProviderReadError(kind="invalid_source")
    items = [_provider_repository(value, workspace) for value in values]
    if get_workspace(session) != workspace:
        raise WorkspaceChanged
    next_page = page.get("next")
    next_cursor = codec.encode_payload({**binding, "next": next_page}) if next_page else None
    return AdminBitbucketRepositoryListResponse(
        workspace=workspace, items=items, next_cursor=next_cursor
    )


async def select_workspace_repository(
    session: Session,
    *,
    actor_id: UUID | None,
    adapter: BitbucketHttpAdapter,
    workspace: str,
    repository_slug: str,
) -> RepositoryRecord:
    configured = _configured_workspace(session)
    workspace, repository_slug = normalize_repository_identity(workspace, repository_slug)
    if workspace != configured:
        raise WorkspaceChanged
    metadata = await adapter.read_repository_metadata(
        session,
        workspace=workspace,
        repository_slug=repository_slug,
    )
    repository = _provider_repository(metadata, workspace)
    if repository.repository_slug != repository_slug:
        raise BitbucketProviderReadError(kind="invalid_source")
    name, name_key = _normalize_descriptive_name(repository.name[:120])
    with session.begin():
        current = session.scalar(
            select(BitbucketConnection).where(BitbucketConnection.id == 1).with_for_update()
        )
        if current is None or current.workspace != workspace:
            raise WorkspaceChanged
        inserted = session.scalar(
            insert(Repository)
            .values(
                id=uuid4(),
                workspace=workspace,
                repository_slug=repository_slug,
                descriptive_name=name,
                descriptive_name_key=name_key,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    Repository.provider,
                    Repository.workspace,
                    Repository.repository_slug,
                ]
            )
            .returning(Repository.id)
        )
        if inserted is not None:
            record_audit(
                session, actor_id=actor_id, action="repository.registered", entity_id=inserted
            )
        saved = session.scalar(
            select(Repository).where(
                Repository.provider == "bitbucket",
                Repository.workspace == workspace,
                Repository.repository_slug == repository_slug,
            )
        )
        assert saved is not None
        return _record(saved)
