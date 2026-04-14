"""
Shared SQLAlchemy base and mixins for all GatherEase models.

Every table gets:
- UUID primary key (generated in Python via uuid.uuid4(), works on any DB)
- created_at  – set on INSERT
- updated_at  – updated automatically on every UPDATE via onupdate
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base. Import this everywhere, not SQLAlchemy's."""
    pass


class TimestampMixin:
    """Adds created_at / updated_at to any model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """UUID primary key generated in Python — compatible with PostgreSQL and SQLite."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,   # Python-side default — no DB function needed
        nullable=False,
    )


class BaseModel(UUIDMixin, TimestampMixin, Base):
    """Convenience base combining UUID PK + timestamps.

    All 12 GatherEase tables inherit from this.
    """

    __abstract__ = True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id}>"
