"""Administrator linking of exact public GitHub repositories."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from verboflex.api.v1.routes.admin_discovery import (
    DISCOVERY_RESPONSES,
    DiscoveryAdapter,
    _failure_response,
)
from verboflex.api.v1.routes.admin_repositories import AdminPrincipal, AdminSession, _response
from verboflex.audit.ledger import record_audit
from verboflex.integrations.bitbucket.client import BitbucketProviderReadError
from verboflex.integrations.github.client import GitHubHttpAdapter, github_identity
from verboflex.integrations.readers import RepositoryReadAdapters
from verboflex.models.repository import Repository
from verboflex.schemas.admin_repositories import AdminRepositoryResponse
from verboflex.services.repositories import _normalize_descriptive_name, _record

router = APIRouter(prefix="/admin/github", tags=["admin-github"])


class GitHubRepositoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner: Annotated[str, Field(min_length=1, max_length=100)]
    repository: Annotated[str, Field(min_length=1, max_length=100)]


class GitHubRepositoryResponse(AdminRepositoryResponse):
    default_branch: str
    stars: int
    language: str | None
    html_url: str
    import_only: bool = True


async def get_github_adapter(adapters: DiscoveryAdapter) -> GitHubHttpAdapter:
    if not isinstance(adapters, RepositoryReadAdapters):
        raise HTTPException(503, "GitHub public import is unavailable")
    return adapters.github


@router.post(
    "/repositories",
    operation_id="connect_admin_github_repository",
    response_model=GitHubRepositoryResponse,
    responses=DISCOVERY_RESPONSES,
)
async def connect_github_repository(
    payload: GitHubRepositoryRequest,
    _principal: AdminPrincipal,
    session: AdminSession,
    adapter: Annotated[GitHubHttpAdapter, Depends(get_github_adapter)],
) -> GitHubRepositoryResponse | JSONResponse:
    try:
        owner, repo = github_identity(payload.owner, payload.repository)
    except ValueError:
        raise HTTPException(422, "Enter a valid GitHub owner and repository name") from None
    try:
        metadata = await adapter.read_repository_metadata(
            session, workspace=owner, repository_slug=repo
        )
    except BitbucketProviderReadError as error:
        return _failure_response(error)
    name, name_key = _normalize_descriptive_name(f"{owner}/{repo}"[:120])
    with session.begin():
        inserted = session.scalar(
            insert(Repository)
            .values(
                id=uuid4(),
                provider="github",
                workspace=owner,
                repository_slug=repo,
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
                session,
                actor_id=_principal.user_id,
                action="repository.registered",
                entity_id=inserted,
            )
        saved = session.scalar(
            select(Repository).where(
                Repository.provider == "github",
                Repository.workspace == owner,
                Repository.repository_slug == repo,
            )
        )
        assert saved is not None
        record = _record(saved)
    return GitHubRepositoryResponse(
        **_response(record).model_dump(),
        default_branch=metadata["default_branch"],
        stars=metadata.get("stargazers_count", 0),
        language=metadata.get("language"),
        html_url=f"https://github.com/{owner}/{repo}",
    )
