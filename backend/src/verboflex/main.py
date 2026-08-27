"""FastAPI application factory boundary."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from verboflex.api.v1.router import api_router
from verboflex.auth.rate_limits import get_redis_client
from verboflex.core.config import get_settings
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.services.bitbucket_oauth import (
    BitbucketOAuthService,
    BitbucketOAuthTokenExchange,
)


@asynccontextmanager
async def _application_lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Own one process-scoped provider connection pool when OAuth is configured."""
    settings = get_settings()
    adapter: BitbucketHttpAdapter | None = None
    try:
        oauth_service = BitbucketOAuthService(
            settings=settings,
            redis_client=get_redis_client(settings),
            token_exchange=BitbucketOAuthTokenExchange(),
        )
        adapter = BitbucketHttpAdapter(
            settings=settings,
            credential_leases=oauth_service,
        )
    except ValueError:
        pass
    application.state.bitbucket_http_adapter = adapter
    try:
        yield
    finally:
        if adapter is not None:
            await adapter.aclose()


def create_app() -> FastAPI:
    """Create the standalone VerboFlex API application."""
    settings = get_settings()
    application = FastAPI(title=settings.app_name, lifespan=_application_lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.unicode_string().removesuffix("/") for origin in settings.cors_origins
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
