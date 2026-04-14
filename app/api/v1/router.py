"""Aggregates all v1 sub-routers under /api/v1."""

from fastapi import APIRouter

from app.api.v1.auth.router import router as auth_router
from app.api.v1.gatherings.router import public_router as invite_router
from app.api.v1.gatherings.router import router as gatherings_router
from app.api.v1.users.router import router as users_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(gatherings_router)
v1_router.include_router(invite_router)
