"""
Async SQLAlchemy engine and session factory.

Uses async_sessionmaker (SQLAlchemy 2.0+) so real-time WebSocket
handlers can share the same session pattern as REST endpoints without
blocking the event loop.

Usage in a FastAPI dependency (see app/dependencies.py):

    async with get_db() as session:
        result = await session.execute(...)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401 — ensures all models register with SQLAlchemy
from app.config import get_settings

_engine: object | None = None
_session_factory: async_sessionmaker | None = None


def _get_engine():  # type: ignore[return]
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,  # detect stale connections automatically
            echo=settings.debug,  # log SQL in development only
        )
    return _engine


def get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # safe for async; avoids lazy-load errors
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession; commit on success, rollback on error."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
