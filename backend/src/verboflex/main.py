"""FastAPI application factory boundary."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Route

from verboflex.api.mcp_oauth import browser_router, oauth_error_handler
from verboflex.api.mcp_oauth import router as oauth_router
from verboflex.api.v1.router import api_router
from verboflex.api.validation import request_validation_error
from verboflex.core.config import get_settings
from verboflex.integrations.readers import create_repository_read_adapters
from verboflex.services.mcp_oauth import OAuthError


@asynccontextmanager
async def _application_lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Own one process-scoped provider connection pool when OAuth is configured."""
    settings = get_settings()
    adapters = create_repository_read_adapters(settings)
    application.state.bitbucket_http_adapter = adapters.bitbucket
    application.state.repository_read_adapters = adapters
    try:
        async with AsyncExitStack() as stack:
            if mcp_app := getattr(application.state, "mcp_app", None):
                await stack.enter_async_context(mcp_app.router.lifespan_context(mcp_app))
            yield
    finally:
        try:
            await adapters.aclose()
        finally:
            application.state.repository_read_adapters = None
            application.state.bitbucket_http_adapter = None


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
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "MCP-Protocol-Version", "Mcp-Session-Id"],
        expose_headers=["WWW-Authenticate", "Mcp-Session-Id"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    application.include_router(browser_router, prefix=settings.api_v1_prefix)
    application.include_router(oauth_router)
    application.add_exception_handler(OAuthError, oauth_error_handler)
    application.add_exception_handler(RequestValidationError, request_validation_error)
    if settings.mcp_public_url:
        from verboflex.mcp_http import McpEndpoint, build_mcp_http

        mcp_app = build_mcp_http(application, settings)
        application.state.mcp_app = mcp_app

        application.router.routes.insert(0, Route("/mcp", endpoint=McpEndpoint(mcp_app)))
    return application


app = create_app()
