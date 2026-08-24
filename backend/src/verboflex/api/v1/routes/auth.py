"""Authentication contract stubs."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from redis import Redis
from sqlalchemy.orm import Session

from verboflex.auth.login import InvalidCredentials, LoginRateLimited, authenticate_login
from verboflex.auth.origin import OriginNotAllowed, enforce_cookie_origin
from verboflex.auth.rate_limits import (
    REFRESH_LIMIT,
    RateLimitUnavailable,
    enforce_auth_action_rate_limit,
    get_redis_client,
)
from verboflex.auth.refresh_sessions import InvalidRefreshSession, rotate_refresh_session
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.schemas.auth import AccessTokenResponse, ChangePasswordRequest
from verboflex.schemas.system import ErrorResponse

router = APIRouter(prefix="/auth", tags=["authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)
OptionalBearerToken = Annotated[str | None, Depends(oauth2_scheme)]
RefreshCookie = Annotated[str | None, Cookie(alias="verboflex_refresh")]
RequestOrigin = Annotated[str | None, Header(alias="Origin")]


@router.post(
    "/token",
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
            client_ip=request.client.host if request.client is not None else "unknown",
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
        response.set_cookie(
            key="verboflex_refresh",
            value=authority.refresh_token,
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
            path="/api/v1/auth",
            secure=settings.refresh_cookie_secure,
            httponly=True,
            samesite="lax",
        )
    return AccessTokenResponse(
        access_token=authority.access_token,
        token_type="bearer",
        expires_in=authority.expires_in,
        must_change_password=authority.must_change_password,
    )


@router.post(
    "/refresh",
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
            identity=refresh_cookie or "missing",
            client_ip=request.client.host if request.client is not None else "unknown",
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

    response.set_cookie(
        key="verboflex_refresh",
        value=authority.refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/api/v1/auth",
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return AccessTokenResponse(
        access_token=authority.access_token,
        token_type="bearer",
        expires_in=authority.expires_in,
        must_change_password=False,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    },
)
async def logout(
    _request: Request,
    _response: Response,
    _session: Annotated[Session, Depends(get_db_session)],
    _redis_client: Annotated[Redis, Depends(get_redis_client)],
    _settings: Annotated[Settings, Depends(get_settings)],
    _refresh_cookie: RefreshCookie = None,
    _origin: RequestOrigin = None,
) -> None:
    """Expose the final idempotent logout signature."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")


@router.post(
    "/change-password",
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
    _request: Request,
    _payload: ChangePasswordRequest,
    _response: Response,
    _access_token: OptionalBearerToken,
    _session: Annotated[Session, Depends(get_db_session)],
    _redis_client: Annotated[Redis, Depends(get_redis_client)],
    _settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Expose the final authenticated password-change signature."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")
