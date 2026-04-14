"""Pydantic schemas for menu and dish endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.enums import DishCategory

# ---------------------------------------------------------------------------
# Dish schemas
# ---------------------------------------------------------------------------


class AddDishRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: DishCategory = DishCategory.OTHER
    assigned_to: str | None = Field(default=None, max_length=255)
    is_host_prepared: bool = True
    servings: int = Field(default=4, ge=1, le=500)
    sort_order: int = Field(default=0, ge=0)


class UpdateDishRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: DishCategory | None = None
    assigned_to: str | None = None
    is_host_prepared: bool | None = None
    servings: int | None = Field(default=None, ge=1, le=500)
    sort_order: int | None = Field(default=None, ge=0)


class DishResponse(BaseModel):
    id: uuid.UUID
    menu_id: uuid.UUID
    name: str
    category: str
    assigned_to: str | None
    is_host_prepared: bool
    servings: int
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Menu schemas
# ---------------------------------------------------------------------------


class MenuResponse(BaseModel):
    id: uuid.UUID
    gathering_id: uuid.UUID
    name: str
    dishes: list[DishResponse]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Safe ORM-to-dict helpers (avoids lazy-load greenlet errors)
# ---------------------------------------------------------------------------


def dish_to_dict(d: object) -> dict:
    return {
        "id": d.id,
        "menu_id": d.menu_id,
        "name": d.name,
        "category": d.category.value if hasattr(d.category, "value") else d.category,
        "assigned_to": d.assigned_to,
        "is_host_prepared": d.is_host_prepared,
        "servings": d.servings,
        "sort_order": d.sort_order,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }
