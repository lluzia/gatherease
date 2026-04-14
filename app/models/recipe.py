"""Recipe — optional recipe attached to a dish.

Stores the full recipe text plus a structured ingredients list
(JSONB on PostgreSQL, JSON on SQLite for tests) so the servings
calculator can scale quantities.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.dish import Dish


class Recipe(BaseModel):
    __tablename__ = "recipes"

    dish_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dishes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one recipe per dish
        index=True,
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured ingredients for the servings scaler.
    # Schema: [{"name": "flour", "quantity": 200, "unit": "g"}, ...]
    # SQLAlchemy's JSON type maps to JSONB on PostgreSQL and JSON on SQLite,
    # so tests work without any dialect-specific handling.
    ingredients: Mapped[list | None] = mapped_column(
        JSON, nullable=True, server_default="[]"
    )

    # Base servings this recipe is written for (scaling reference)
    base_servings: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    dish: Mapped[Dish] = relationship("Dish", back_populates="recipe")
