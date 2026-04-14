"""PrepTask — a preparation task on the gathering's timeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.gathering import Gathering


class PrepTask(BaseModel):
    __tablename__ = "prep_tasks"

    gathering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gatherings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    is_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Relationships
    gathering: Mapped[Gathering] = relationship(
        "Gathering", back_populates="prep_tasks"
    )
