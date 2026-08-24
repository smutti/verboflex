"""Versioned API router composition."""

from fastapi import APIRouter

from verboflex.api.v1.routes import auth, health, system, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(system.router)
