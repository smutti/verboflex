"""FastAPI application factory boundary."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from verboflex.api.v1.router import api_router
from verboflex.core.config import get_settings


def create_app() -> FastAPI:
    """Create the standalone VerboFlex API application."""
    settings = get_settings()
    application = FastAPI(title=settings.app_name)
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
