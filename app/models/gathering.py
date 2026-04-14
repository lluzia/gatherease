"""Gathering model — the core entity of GatherEase."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.budget import Budget
    from app.models.guest_rsvp import GuestRSVP
    from app.models.menu import Menu
    from app.models.prep_task import PrepTask
    from app.models.reminder import Reminder
    from app.models.user import User


class Gathering(BaseModel):
    """A home gathering event hosted by a registered user."""

    __tablename__ = "gatherings"

    host_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    guest_count_estimate: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Invite / public page
    invite_token: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True, index=True
    )

    # Host visibility toggles for the public guest page
    show_menu: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    show_location: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    show_shopping_list: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    show_prep_tasks: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Relationships
    host: Mapped["User"] = relationship("User", back_populates="gatherings")
    guest_rsvps: Mapped[list["GuestRSVP"]] = relationship(
        "GuestRSVP", back_populates="gathering", lazy="raise", cascade="all, delete-orphan"
    )
    menus: Mapped[list["Menu"]] = relationship(
        "Menu", back_populates="gathering", lazy="raise", cascade="all, delete-orphan"
    )
    prep_tasks: Mapped[list["PrepTask"]] = relationship(
        "PrepTask", back_populates="gathering", lazy="raise", cascade="all, delete-orphan"
    )
    budget: Mapped["Budget | None"] = relationship(
        "Budget", back_populates="gathering", lazy="raise", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        "Reminder", back_populates="gathering", lazy="raise", cascade="all, delete-orphan"
    )
