"""BudgetEntry — an individual spend line within a budget."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.enums import BudgetEntryType, pg_enum
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.budget import Budget


class BudgetEntry(BaseModel):
    __tablename__ = "budget_entries"

    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("budgets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_type: Mapped[BudgetEntryType] = mapped_column(
        pg_enum(BudgetEntryType, "budget_entry_type"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    paid_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    budget: Mapped[Budget] = relationship("Budget", back_populates="entries")
