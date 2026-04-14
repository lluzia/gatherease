"""ShoppingItem — one line on the gathering's shopping list.

Items can be auto-generated from recipe ingredients or manually added.
They can optionally be linked back to the dish that generated them.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.dish import Dish


class ShoppingItem(BaseModel):
    __tablename__ = "shopping_items"

    gathering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gatherings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable — manually added items are not linked to a dish
    dish_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dishes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Who is responsible for buying this item
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_purchased: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", index=True
    )
    # True when generated from a recipe ingredient; False when manually added
    is_auto_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Relationships
    dish: Mapped[Dish | None] = relationship("Dish", back_populates="shopping_items")
