"""Authentication contract stubs."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from redis import Redis
from sqlalchemy.orm import Session

from verboflex.auth.login import InvalidCredentials, LoginRateLimited, authenticate_login
from verboflex.auth.origin import OriginNotAllowed, enforce_cookie_origin
from verboflex.auth.password_change import (
    IncorrectCurrentPassword,
    InvalidPasswordChangePrincipal,
    PasswordChangePolicyError,
    decode_password_change_candidate,
    replace_current_password,
)
from verboflex.auth.rate_limits import (
    LOGOUT_LIMIT,
    PASSWORD_CHANGE_LIMIT,
    REFRESH_LIMIT,
    RateLimitUnavailable,
    enforce_auth_action_rate_limit,
    get_redis_client,
    validated_client_ip,
)
from verboflex.auth.refresh_sessions import (
    InvalidRefreshSession,
    refresh_rate_limit_identity,
    revoke_refresh_session,
    rotate_refresh_session,
)
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.schemas.auth import AccessTokenResponse, ChangePasswordRequest
from verboflex.schemas.system import ErrorResponse

router = APIRouter(prefix="/auth", tags=["authentication"])
REFRESH_COOKIE_NAME = "__Host-verboflex_refresh"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)
OptionalBearerToken = Annotated[str | None, Depends(oauth2_scheme)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)]
RequestOrigin = Annotated[str | None, Header(alias="Origin")]


def _set_refresh_cookie(response: Response, refresh_token: str, settings: Settings) -> None:
    """Set refresh authority with the one approved cookie scope."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear refresh authority with attributes matching the set-cookie scope."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


@router.post(
    "/token",
    operation_id="issue_token",
    response_model=AccessTokenResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def issue_token(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_db_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccessTokenResponse:
    """Expose the final login request and response signature."""
    try:
        authority = authenticate_login(
            session,
            redis_client,
            email=form_data.username,
            password=form_data.password,
            client_ip=validated_client_ip(request),
            settings=settings,
        )
    except InvalidCredentials as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except LoginRateLimited as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(error.retry_after),
                "X-RateLimit-Remaining": "0",
            },
        ) from error
    except RateLimitUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from error

    if authority.refresh_token is not None:
        _set_refresh_cookie(response, authority.refresh_token, settings)
    return AccessTokenResponse(
        access_token=authority.access_token,
        token_type="bearer",
        expires_in=authority.expires_in,
        must_change_password=authority.must_change_password,
    )


@router.post(
    "/refresh",
    operation_id="refresh_access_token",
    response_model=AccessTokenResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def refresh_access_token(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_cookie: RefreshCookie = None,
    origin: RequestOrigin = None,
) -> AccessTokenResponse:
    """Expose the final cookie-rotation request and response signature."""
    try:
        enforce_cookie_origin(origin, settings=settings)
        limit = enforce_auth_action_rate_limit(
            redis_client,
            action="refresh",
            identity=refresh_rate_limit_identity(session, refresh_cookie),
            client_ip=validated_client_ip(request),
            limit=REFRESH_LIMIT,
        )
        if not limit.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "Retry-After": str(limit.retry_after),
                    "X-RateLimit-Remaining": "0",
                },
            )
        authority = rotate_refresh_session(
            session,
            refresh_cookie,
            settings=settings,
        )
    except OriginNotAllowed as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed",
        ) from error
    except RateLimitUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from error
    except InvalidRefreshSession as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh session",
        ) from error

    _set_refresh_cookie(response, authority.refresh_token, settings)
    return AccessTokenResponse(
        access_token=authority.access_token,
        token_type="bearer",
        expires_in=authority.expires_in,
        must_change_password=False,
    )


@router.post(
    "/logout",
    operation_id="logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    },
)
async def logout(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_cookie: RefreshCookie = None,
    origin: RequestOrigin = None,
) -> None:
    """Expose the final idempotent logout signature."""
    try:
        enforce_cookie_origin(origin, settings=settings)
    except OriginNotAllowed as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed",
        ) from error

    try:
        limit = enforce_auth_action_rate_limit(
            redis_client,
            action="logout",
            identity=refresh_cookie or "missing",
            client_ip=validated_client_ip(request),
            limit=LOGOUT_LIMIT,
        )
    except RateLimitUnavailable:
        limit = None
    if limit is not None and not limit.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(limit.retry_after),
                "X-RateLimit-Remaining": "0",
            },
        )

    revoke_refresh_session(session, refresh_cookie)
    _clear_refresh_cookie(response)


@router.post(
    "/change-password",
    operation_id="change_password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    response: Response,
    access_token: OptionalBearerToken,
    session: Annotated[Session, Depends(get_db_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Expose the final authenticated password-change signature."""
    try:
        candidate = decode_password_change_candidate(access_token, settings=settings)
    except InvalidPasswordChangePrincipal as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    try:
        limit = enforce_auth_action_rate_limit(
            redis_client,
            action="password-change",
            identity=candidate.rate_limit_identity,
            client_ip=validated_client_ip(request),
            limit=PASSWORD_CHANGE_LIMIT,
        )
    except RateLimitUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from error
    if not limit.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(limit.retry_after),
                "X-RateLimit-Remaining": "0",
            },
        )

    try:
        replace_current_password(
            session,
            candidate,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except InvalidPasswordChangePrincipal as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except IncorrectCurrentPassword as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        ) from error
    except PasswordChangePolicyError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    _clear_refresh_cookie(response)
