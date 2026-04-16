"""
Alembic migration environment — async SQLAlchemy 2.0 compatible.

Run migrations:
    alembic upgrade head
    alembic downgrade -1
    alembic revision --autogenerate -m "description"
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import get_settings

# Import Base and all models so Alembic can detect every table for autogenerate.
# Order matters only for readability — SQLAlchemy resolves FK dependencies itself.
from app.models.base import Base  # noqa: F401 — registers Base.metadata
from app.models.budget import Budget  # noqa: F401
from app.models.budget_entry import BudgetEntry  # noqa: F401
from app.models.dish import Dish  # noqa: F401
from app.models.gathering import Gathering  # noqa: F401
from app.models.guest_rsvp import GuestRSVP  # noqa: F401
from app.models.menu import Menu  # noqa: F401
from app.models.prep_task import PrepTask  # noqa: F401
from app.models.recipe import Recipe  # noqa: F401
from app.models.reminder import Reminder  # noqa: F401
from app.models.shopping_item import ShoppingItem  # noqa: F401
from app.models.user import User  # noqa: F401

config = context.config
settings = get_settings()

# Override sqlalchemy.url from alembic.ini with our settings value
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode (generates SQL without connecting)
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode (connects to the DB)
# ---------------------------------------------------------------------------


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
