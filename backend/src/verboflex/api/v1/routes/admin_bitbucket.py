"""Administrator lifecycle routes for one organizational Bitbucket connection."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from pydantic import AnyHttpUrl
from redis import Redis
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal, require_roles
from verboflex.auth.rate_limits import get_redis_client
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.schemas.admin_bitbucket import (
    AdminBitbucketAuthorizationResponse,
    AdminBitbucketErrorResponse,
    AdminBitbucketStatusResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import RoleName
from verboflex.services.bitbucket_oauth import (
    BitbucketConnectionPublicStatus,
    BitbucketOAuthService,
    BitbucketOAuthTokenExchange,
    OAuthCallbackRejected,
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
CALLBACK_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": AdminBitbucketErrorResponse},
    **UNAVAILABLE_RESPONSE,
}
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


def get_bitbucket_oauth_service(
    settings: Annotated[Settings, Depends(get_settings)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> BitbucketOAuthService | None:
    """Build the configured backend-only OAuth authority or report unavailable."""
    try:
        return BitbucketOAuthService(
            settings=settings,
            redis_client=redis_client,
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bitbucket connection unavailable",
        )
    return service


def _session_id(principal: Principal) -> UUID:
    if principal.session_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bitbucket connection unavailable",
        )
    return principal.session_id


def _status_response(snapshot: BitbucketConnectionPublicStatus) -> AdminBitbucketStatusResponse:
    return AdminBitbucketStatusResponse(
        status=STATUS_LABELS[snapshot.state],
        connected_at=snapshot.connected_at,
        expires_at=snapshot.expires_at,
        revoked_at=snapshot.revoked_at,
    )


def _authorization_response(
    service: BitbucketOAuthService,
    session: Session,
    principal: Principal,
) -> AdminBitbucketAuthorizationResponse:
    state = service.start_current(
        session,
        admin_id=principal.user_id,
        session_id=_session_id(principal),
    )
    return AdminBitbucketAuthorizationResponse(
        authorization_url=AnyHttpUrl(service.authorization_url(state)),
        state_expires_in=600,
    )


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
    response.headers["Cache-Control"] = "no-store"
    if service is None:
        return AdminBitbucketStatusResponse(
            status="Unavailable",
            connected_at=None,
            expires_at=None,
            revoked_at=None,
        )
    return _status_response(service.public_status(session))


@router.post(
    "/oauth/start",
    operation_id="start_admin_bitbucket_oauth",
    response_model=AdminBitbucketAuthorizationResponse,
    responses=PROTECTED_RESPONSES,
)
async def start_admin_bitbucket_oauth(
    principal: AdminPrincipal,
    session: AdminSession,
    service: ConfiguredOAuthService,
) -> AdminBitbucketAuthorizationResponse:
    """Start one exact static-consumer repository-read authorization flow."""
    return _authorization_response(_configured(service), session, principal)


@router.post(
    "/oauth/reconnect",
    operation_id="reconnect_admin_bitbucket_oauth",
    response_model=AdminBitbucketAuthorizationResponse,
    responses=PROTECTED_RESPONSES,
)
async def reconnect_admin_bitbucket_oauth(
    principal: AdminPrincipal,
    session: AdminSession,
    service: ConfiguredOAuthService,
) -> AdminBitbucketAuthorizationResponse:
    """Replace authority only after a new state-bound callback succeeds."""
    return _authorization_response(_configured(service), session, principal)


@router.get(
    "/oauth/callback",
    operation_id="complete_admin_bitbucket_oauth_callback",
    status_code=status.HTTP_303_SEE_OTHER,
    response_class=RedirectResponse,
    responses=CALLBACK_RESPONSES,
)
async def complete_admin_bitbucket_oauth_callback(
    session: AdminSession,
    service: ConfiguredOAuthService,
    settings: Annotated[Settings, Depends(get_settings)],
    state_value: Annotated[str, Query(alias="state", min_length=1, max_length=512)],
    code: Annotated[str, Query(min_length=1, max_length=2048)],
) -> RedirectResponse:
    """Consume state authority and return through one fixed same-tab redirect."""
    configured = _configured(service)
    try:
        result = configured.complete_callback_from_state(
            session,
            state=state_value,
            code=code,
            callback_uri=str(settings.bitbucket_oauth_callback_uri),
            post_callback_path=settings.bitbucket_oauth_post_callback_path,
        )
    except OAuthCallbackRejected as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth callback rejected",
        ) from error
    except OAuthConnectionUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bitbucket connection unavailable",
        ) from error
    return RedirectResponse(
        url=result.redirect_path,
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Cache-Control": "no-store"},
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
    configured.revoke_current(session, actor_id=principal.user_id)
    response.headers["Cache-Control"] = "no-store"
    return _status_response(configured.public_status(session))
