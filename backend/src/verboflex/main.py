"""FastAPI application factory boundary."""

from fastapi import FastAPI

from verboflex.api.v1.router import api_router
from verboflex.core.config import get_settings


def create_app() -> FastAPI:
    """Create the standalone VerboFlex API application."""
    settings = get_settings()
    application = FastAPI(title=settings.app_name)
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
