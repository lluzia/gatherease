"""Menu — one gathering can have one active menu."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.dish import Dish
    from app.models.gathering import Gathering


class Menu(BaseModel):
    __tablename__ = "menus"

    gathering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gatherings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # A gathering could have drafts — name distinguishes them
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="Menu"
    )

    # Relationships
    gathering: Mapped[Gathering] = relationship("Gathering", back_populates="menus")
    dishes: Mapped[list[Dish]] = relationship(
        "Dish", back_populates="menu", lazy="raise", cascade="all, delete-orphan"
    )
