"""Schemas for budget endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SetBudgetRequest(BaseModel):
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    host_budget_limit: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    participant_target: Decimal | None = Field(default=None, ge=0, decimal_places=2)


class AddEntryRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=0, decimal_places=2)
    paid_by: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)


class BudgetEntryResponse(BaseModel):
    id: uuid.UUID
    description: str
    amount: Decimal
    paid_by: str | None
    notes: str | None
    entry_type: str
    created_at: datetime


class BudgetResponse(BaseModel):
    id: uuid.UUID
    gathering_id: uuid.UUID
    currency: str
    host_budget_limit: Decimal | None
    participant_target: Decimal | None
    host_total_spent: Decimal
    participant_total_spent: Decimal
    total_spent: Decimal
    host_remaining: Decimal | None  # None if no limit set
    version: int
    entries: list[BudgetEntryResponse]


def entry_to_dict(e: object) -> dict:
    return {
        "id": e.id,
        "description": e.description,
        "amount": e.amount,
        "paid_by": e.paid_by,
        "notes": e.notes,
        "entry_type": (
            e.entry_type.value if hasattr(e.entry_type, "value") else e.entry_type
        ),
        "created_at": e.created_at,
    }
