"""Administrator lifecycle routes for one organizational Bitbucket connection."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal, require_roles
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.schemas.admin_bitbucket import (
    AdminBitbucketErrorResponse,
    AdminBitbucketStatusResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import RoleName
from verboflex.services.bitbucket_oauth import (
    BitbucketConnectionPublicStatus,
    BitbucketOAuthService,
    BitbucketOAuthTokenExchange,
    OAuthConnectionUnavailable,
)

router = APIRouter(prefix="/admin/bitbucket", tags=["admin-bitbucket"])
AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]
AdminSession = Annotated[Session, Depends(get_db_session, use_cache=False)]
AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
}
UNAVAILABLE_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": AdminBitbucketErrorResponse},
}
PROTECTED_RESPONSES = {**AUTH_RESPONSES, **UNAVAILABLE_RESPONSE}
PublicConnectionState = Literal[
    "disconnected",
    "connected",
    "reauthorization_required",
    "unavailable",
]
PublicConnectionLabel = Literal[
    "Disconnected",
    "Connected",
    "Reauthorization required",
    "Unavailable",
]
STATUS_LABELS: dict[PublicConnectionState, PublicConnectionLabel] = {
    "disconnected": "Disconnected",
    "connected": "Connected",
    "reauthorization_required": "Reauthorization required",
    "unavailable": "Unavailable",
}
NO_STORE_HEADERS = {"Cache-Control": "no-store"}


def get_bitbucket_oauth_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> BitbucketOAuthService | None:
    """Build the configured backend-only provider authority or report unavailable."""
    try:
        return BitbucketOAuthService(
            settings=settings,
            token_exchange=BitbucketOAuthTokenExchange(),
        )
    except ValueError:
        return None


ConfiguredOAuthService = Annotated[
    BitbucketOAuthService | None,
    Depends(get_bitbucket_oauth_service),
]


def _configured(service: BitbucketOAuthService | None) -> BitbucketOAuthService:
    if service is None:
        raise _unavailable()
    return service


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Bitbucket connection unavailable",
        headers=NO_STORE_HEADERS,
    )


def _status_response(snapshot: BitbucketConnectionPublicStatus) -> AdminBitbucketStatusResponse:
    return AdminBitbucketStatusResponse(
        status=STATUS_LABELS[snapshot.state],
        connected_at=snapshot.connected_at,
        expires_at=snapshot.expires_at,
        revoked_at=snapshot.revoked_at,
    )


def _connect(
    *,
    response: Response,
    principal: Principal,
    session: Session,
    service: BitbucketOAuthService | None,
) -> AdminBitbucketStatusResponse:
    configured = _configured(service)
    try:
        configured.acquire_client_credentials(session, actor_id=principal.user_id)
        snapshot = configured.public_status(session)
    except OAuthConnectionUnavailable as error:
        raise _unavailable() from error
    response.headers.update(NO_STORE_HEADERS)
    return _status_response(snapshot)


@router.get(
    "",
    operation_id="get_admin_bitbucket_status",
    response_model=AdminBitbucketStatusResponse,
    responses=PROTECTED_RESPONSES,
)
async def get_admin_bitbucket_status(
    response: Response,
    _principal: AdminPrincipal,
    session: AdminSession,
    service: ConfiguredOAuthService,
) -> AdminBitbucketStatusResponse:
    """Return one no-store status containing no provider credential metadata."""
    response.headers.update(NO_STORE_HEADERS)
    if service is None:
        return AdminBitbucketStatusResponse(
            status="Unavailable",
            connected_at=None,
            expires_at=None,
            revoked_at=None,
        )
    return _status_response(service.public_status(session))


@router.post(
    "/connect",
    operation_id="connect_admin_bitbucket_oauth",
    response_model=AdminBitbucketStatusResponse,
    responses=PROTECTED_RESPONSES,
)
async def connect_admin_bitbucket_oauth(
    response: Response,
    principal: AdminPrincipal,
    session: AdminSession,
    service: ConfiguredOAuthService,
) -> AdminBitbucketStatusResponse:
    """Acquire one backend-only, read-only client-credentials generation."""
    return _connect(
        response=response,
        principal=principal,
        session=session,
        service=service,
    )


@router.post(
    "/reconnect",
    operation_id="reconnect_admin_bitbucket_oauth",
    response_model=AdminBitbucketStatusResponse,
    responses=PROTECTED_RESPONSES,
)
async def reconnect_admin_bitbucket_oauth(
    response: Response,
    principal: AdminPrincipal,
    session: AdminSession,
    service: ConfiguredOAuthService,
) -> AdminBitbucketStatusResponse:
    """Replace current authority with one newly acquired access-only generation."""
    return _connect(
        response=response,
        principal=principal,
        session=session,
        service=service,
    )


@router.post(
    "/revoke",
    operation_id="revoke_admin_bitbucket_connection_locally",
    response_model=AdminBitbucketStatusResponse,
    responses=PROTECTED_RESPONSES,
)
async def revoke_admin_bitbucket_connection_locally(
    response: Response,
    principal: AdminPrincipal,
    session: AdminSession,
    service: ConfiguredOAuthService,
) -> AdminBitbucketStatusResponse:
    """Immediately invalidate local credentials without a provider revoke claim."""
    configured = _configured(service)
    try:
        configured.revoke_current(session, actor_id=principal.user_id)
        snapshot = configured.public_status(session)
    except OAuthConnectionUnavailable as error:
        raise _unavailable() from error
    response.headers.update(NO_STORE_HEADERS)
    return _status_response(snapshot)
