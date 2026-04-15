"""
GatherEase FastAPI application entry point.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.budget.router import ws_router as budget_ws_router
from app.api.v1.router import v1_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(debug=settings.debug)
    logger.info(
        "startup",
        app=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
    )
    yield
    logger.info("shutdown", app=settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="GatherEase API",
        description="Backend API for GatherEase — Organise gatherings. Share budgets. Enjoy together.",
        version=settings.app_version,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=(
            ["*"]
            if not settings.is_production
            else [str(o) for o in settings.cors_origins]
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(v1_router)
    # WebSocket router mounted at root — path stays /ws/gatherings/{id}/budget
    # (no /api/v1 prefix, matching client expectations and the handoff docs)
    app.include_router(budget_ws_router)

    @app.get("/health", tags=["Health"], include_in_schema=False)
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
        }

    return app


# ---------------------------------------------------------------------------
# ASGI entrypoint — module-level app for uvicorn
# Only created when running the server, NOT during test imports.
# Tests import create_app() directly from conftest.py after setting env vars.
# ---------------------------------------------------------------------------
app = create_app()
