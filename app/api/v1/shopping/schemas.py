"""Schemas for shopping list endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AddShoppingItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=50)
    assigned_to: str | None = Field(default=None, max_length=255)


class UpdateShoppingItemRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None
    assigned_to: str | None = None
    is_purchased: bool | None = None


class ShoppingItemResponse(BaseModel):
    id: uuid.UUID
    gathering_id: uuid.UUID
    name: str
    quantity: float | None
    unit: str | None
    assigned_to: str | None
    is_purchased: bool
    is_auto_generated: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShoppingListResponse(BaseModel):
    items: list[ShoppingItemResponse]
    total: int
    purchased: int
    remaining: int


def _to_bool(v: object) -> bool:
    """Normalise SQLite boolean strings ('false'/'true') to Python bool."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() == "true"
    return bool(v)


def item_to_dict(i: object) -> dict:
    return {
        "id": i.id,
        "gathering_id": i.gathering_id,
        "name": i.name,
        "quantity": float(i.quantity) if i.quantity is not None else None,
        "unit": i.unit,
        "assigned_to": i.assigned_to,
        "is_purchased": _to_bool(i.is_purchased),
        "is_auto_generated": _to_bool(i.is_auto_generated),
        "created_at": i.created_at,
        "updated_at": i.updated_at,
    }
