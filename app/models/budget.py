"""Budget — the financial plan for a gathering.

One budget per gathering. Tracks the host's planned spend ceiling
alongside real-time actual spend derived from budget entries.

The dual-budget model from the PRD:
  - host_budget_limit  → what the host is willing to spend total
  - participant_target → optional per-head contribution target
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.budget_entry import BudgetEntry
    from app.models.gathering import Gathering


class Budget(BaseModel):
    __tablename__ = "budgets"

    gathering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gatherings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one budget per gathering
        index=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="EUR"
    )
    host_budget_limit: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    # Target contribution per participant (optional)
    participant_target: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    # Optimistic locking — incremented on every budget update to prevent
    # concurrent overwrites (race condition guard for real-time sync)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    # Relationships
    gathering: Mapped[Gathering] = relationship("Gathering", back_populates="budget")
    entries: Mapped[list[BudgetEntry]] = relationship(
        "BudgetEntry",
        back_populates="budget",
        lazy="raise",
        cascade="all, delete-orphan",
    )
