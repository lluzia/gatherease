"""Reminder — a scheduled notification for a gathering."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.enums import ReminderType, pg_enum
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.gathering import Gathering


class Reminder(BaseModel):
    __tablename__ = "reminders"

    gathering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gatherings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_type: Mapped[ReminderType] = mapped_column(
        pg_enum(ReminderType, "reminder_type"),
        nullable=False,
        server_default=ReminderType.PUSH.value,
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    is_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    gathering: Mapped[Gathering] = relationship("Gathering", back_populates="reminders")
