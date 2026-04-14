"""Dish — a single item on a menu."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.enums import DishCategory, pg_enum
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.menu import Menu
    from app.models.recipe import Recipe
    from app.models.shopping_item import ShoppingItem


class Dish(BaseModel):
    __tablename__ = "dishes"

    menu_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[DishCategory] = mapped_column(
        pg_enum(DishCategory, "dish_category"),
        nullable=False,
        server_default=DishCategory.OTHER.value,
        index=True,
    )
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_host_prepared: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    servings: Mapped[int] = mapped_column(Integer, nullable=False, server_default="4")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    menu: Mapped["Menu"] = relationship("Menu", back_populates="dishes")
    recipe: Mapped["Recipe | None"] = relationship(
        "Recipe", back_populates="dish", lazy="raise", cascade="all, delete-orphan"
    )
    shopping_items: Mapped[list["ShoppingItem"]] = relationship(
        "ShoppingItem", back_populates="dish", lazy="raise"
    )
