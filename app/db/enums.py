"""
Central enum definitions for GatherEase.

All Python enums live here. All SQLAlchemy column types use pg_enum()
which sets create_type=False — meaning SQLAlchemy never tries to CREATE
the type in the database. That job belongs exclusively to Alembic migrations.

Usage in models:
    from app.db.enums import RSVPStatus, pg_enum

    status: Mapped[RSVPStatus] = mapped_column(
        pg_enum(RSVPStatus, "rsvp_status"),
        nullable=False,
        server_default=RSVPStatus.PENDING.value,
    )
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum


# ---------------------------------------------------------------------------
# Python enum classes
# ---------------------------------------------------------------------------

class RSVPStatus(str, enum.Enum):
    ACCEPTED = "accepted"
    DECLINED = "declined"
    MAYBE    = "maybe"
    PENDING  = "pending"


class DishCategory(str, enum.Enum):
    STARTER  = "starter"
    MAIN     = "main"
    SIDE     = "side"
    DESSERT  = "dessert"
    DRINK    = "drink"
    OTHER    = "other"


class BudgetEntryType(str, enum.Enum):
    HOST        = "host"
    PARTICIPANT = "participant"


class ReminderType(str, enum.Enum):
    PUSH  = "push"
    EMAIL = "email"
    BOTH  = "both"


# ---------------------------------------------------------------------------
# Helper — always create_type=False so models never touch pg_type
# ---------------------------------------------------------------------------

def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Return a SQLAlchemy Enum that reuses an existing PG type.

    create_type=False means: "the type already exists in the DB
    (created by a migration) — do NOT try to CREATE it again."
    """
    return Enum(enum_cls, name=name, create_type=False)
