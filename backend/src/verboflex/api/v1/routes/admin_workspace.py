"""Administrator workspace configuration and bounded Bitbucket repository picker."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from verboflex.api.v1.routes.admin_discovery import (
    DISCOVERY_RESPONSES,
    AdminPrincipal,
    AdminSession,
    DiscoveryAdapter,
    _failure_response,
)
from verboflex.auth.rate_limits import (
    BoundedLocalRateLimiter,
    get_local_rate_limiter,
    raise_rate_limited,
)
from verboflex.core.config import Settings, get_settings
from verboflex.integrations.bitbucket.client import BitbucketProviderReadError
from verboflex.integrations.readers import RepositoryReadAdapters
from verboflex.schemas.admin_repositories import AdminRepositoryResponse
from verboflex.schemas.admin_workspace import (
    AdminBitbucketRepositoryListResponse,
    AdminWorkspaceRequest,
    AdminWorkspaceResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.services.signed_cursor import InvalidSignedCursor
from verboflex.services.workspace_repositories import (
    WorkspaceChanged,
    WorkspaceRequired,
    get_workspace,
    list_workspace_repositories,
    select_workspace_repository,
    set_workspace,
)

router = APIRouter(prefix="/admin/bitbucket", tags=["admin-bitbucket"])
RESPONSES = {**DISCOVERY_RESPONSES, 409: {"model": ErrorResponse}, 429: {"model": ErrorResponse}}


def limit_workspace_requests(
    principal: AdminPrincipal,
    response: Response,
    limiter: Annotated[BoundedLocalRateLimiter, Depends(get_local_rate_limiter)],
) -> None:
    result = limiter.check(f"workspace-picker:{principal.user_id}", limit=60, window_seconds=60)
    if not result.allowed:
        raise_rate_limited(result)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["Cache-Control"] = "no-store"


@router.get(
    "/workspace",
    operation_id="get_admin_bitbucket_workspace",
    response_model=AdminWorkspaceResponse,
    responses=RESPONSES,
    dependencies=[Depends(limit_workspace_requests)],
)
async def read_workspace(
    _principal: AdminPrincipal, session: AdminSession
) -> AdminWorkspaceResponse:
    return AdminWorkspaceResponse(workspace=get_workspace(session))


@router.put(
    "/workspace",
    operation_id="update_admin_bitbucket_workspace",
    response_model=AdminWorkspaceResponse,
    responses=RESPONSES,
    dependencies=[Depends(limit_workspace_requests)],
)
async def update_workspace(
    payload: AdminWorkspaceRequest, _principal: AdminPrincipal, session: AdminSession
) -> AdminWorkspaceResponse:
    return AdminWorkspaceResponse(
        workspace=set_workspace(session, payload.workspace, actor_id=_principal.user_id)
    )


def _configuration_error(error: WorkspaceRequired | WorkspaceChanged) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail=(
            "Configure a Bitbucket workspace first"
            if isinstance(error, WorkspaceRequired)
            else "Bitbucket workspace changed; reload repositories"
        ),
    )


@router.get(
    "/repositories",
    operation_id="list_admin_bitbucket_repositories",
    response_model=AdminBitbucketRepositoryListResponse,
    responses=RESPONSES,
    dependencies=[Depends(limit_workspace_requests)],
)
async def list_repositories(
    principal: AdminPrincipal,
    session: AdminSession,
    adapter: DiscoveryAdapter,
    settings: Annotated[Settings, Depends(get_settings)],
    q: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
) -> AdminBitbucketRepositoryListResponse | JSONResponse:
    adapter = adapter.bitbucket if isinstance(adapter, RepositoryReadAdapters) else adapter
    if adapter is None or settings.jwt_secret_key is None:
        return _failure_response(BitbucketProviderReadError(kind="unavailable"))
    try:
        return await list_workspace_repositories(
            session,
            adapter=adapter,
            principal_id=principal.user_id,
            secret=settings.jwt_secret_key.get_secret_value(),
            query=q,
            limit=limit,
            cursor=cursor,
        )
    except (WorkspaceRequired, WorkspaceChanged) as error:
        raise _configuration_error(error) from error
    except (InvalidSignedCursor, ValueError) as error:
        raise HTTPException(status_code=422, detail="Invalid repository query or cursor") from error
    except BitbucketProviderReadError as error:
        return _failure_response(error)


@router.put(
    "/repositories/{repository_slug}",
    operation_id="select_admin_bitbucket_repository",
    response_model=AdminRepositoryResponse,
    responses=RESPONSES,
    dependencies=[Depends(limit_workspace_requests)],
)
async def select_repository(
    repository_slug: str,
    payload: AdminWorkspaceRequest,
    _principal: AdminPrincipal,
    session: AdminSession,
    adapter: DiscoveryAdapter,
) -> AdminRepositoryResponse | JSONResponse:
    adapter = adapter.bitbucket if isinstance(adapter, RepositoryReadAdapters) else adapter
    if adapter is None:
        return _failure_response(BitbucketProviderReadError(kind="unavailable"))
    try:
        record = await select_workspace_repository(
            session,
            adapter=adapter,
            workspace=payload.workspace,
            repository_slug=repository_slug,
            actor_id=_principal.user_id,
        )
    except (WorkspaceRequired, WorkspaceChanged) as error:
        raise _configuration_error(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid repository identity") from error
    except BitbucketProviderReadError as error:
        return _failure_response(error)
    return AdminRepositoryResponse(
        id=record.id,
        workspace=record.workspace,
        repository_slug=record.repository_slug,
        descriptive_name=record.descriptive_name,
    )
