"""Versioned API router composition."""

from fastapi import APIRouter

from verboflex.api.v1.routes import (
    admin_products,
    admin_repositories,
    admin_users,
    auth,
    health,
    system,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(system.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_products.router)
api_router.include_router(admin_repositories.router)
