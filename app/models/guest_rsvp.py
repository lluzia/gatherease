"""GuestRSVP — tracks guest responses to a gathering invite."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.enums import RSVPStatus, pg_enum
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.gathering import Gathering


class GuestRSVP(BaseModel):
    __tablename__ = "guest_rsvps"

    gathering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gatherings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[RSVPStatus] = mapped_column(
        pg_enum(RSVPStatus, "rsvp_status"),
        nullable=False,
        server_default=RSVPStatus.PENDING.value,
        index=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    gathering: Mapped["Gathering"] = relationship(
        "Gathering", back_populates="guest_rsvps"
    )
