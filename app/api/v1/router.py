"""Aggregates all v1 sub-routers under /api/v1.

Note: the WebSocket router (ws_router) is intentionally NOT included here.
It must be mounted at the application root (no /api/v1 prefix) in main.py
so the path stays  ws://host/ws/gatherings/{id}/budget  as documented.
"""

from fastapi import APIRouter

from app.api.v1.auth.router import router as auth_router
from app.api.v1.budget.router import router as budget_router
from app.api.v1.gatherings.router import public_router as invite_router
from app.api.v1.gatherings.router import router as gatherings_router
from app.api.v1.menus.router import router as menus_router
from app.api.v1.prep.router import router as prep_router
from app.api.v1.shopping.router import router as shopping_router
from app.api.v1.users.router import router as users_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(gatherings_router)
v1_router.include_router(invite_router)
v1_router.include_router(menus_router)
v1_router.include_router(shopping_router)
v1_router.include_router(prep_router)
v1_router.include_router(budget_router)
