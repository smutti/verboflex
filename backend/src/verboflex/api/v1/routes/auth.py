"""Authentication contract stubs."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from redis import Redis
from sqlalchemy.orm import Session

from verboflex.auth.rate_limits import get_redis_client
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
    _request: Request,
    _response: Response,
    _form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    _session: Annotated[Session, Depends(get_db_session)],
    _redis_client: Annotated[Redis, Depends(get_redis_client)],
    _settings: Annotated[Settings, Depends(get_settings)],
) -> AccessTokenResponse:
    """Expose the final login request and response signature."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")


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
    _response: Response,
    _refresh_cookie: RefreshCookie = None,
    _origin: RequestOrigin = None,
) -> AccessTokenResponse:
    """Expose the final cookie-rotation request and response signature."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    },
)
async def logout(
    _response: Response,
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
    _payload: ChangePasswordRequest,
    _response: Response,
    _access_token: OptionalBearerToken,
) -> None:
    """Expose the final authenticated password-change signature."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")
