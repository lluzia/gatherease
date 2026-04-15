"""Schemas for the reminders endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.enums import ReminderType


class CreateReminderRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str | None = Field(default=None, max_length=1000)
    reminder_type: ReminderType = ReminderType.PUSH
    scheduled_at: datetime = Field(
        description="UTC datetime when this reminder should fire."
    )

    @field_validator("scheduled_at")
    @classmethod
    def must_be_future(cls, v: datetime) -> datetime:
        from datetime import UTC

        now = datetime.now(UTC)
        # Make v timezone-aware if it arrives naive (treat as UTC)
        if v.tzinfo is None:
            from datetime import timezone

            v = v.replace(tzinfo=timezone.utc)
        if v <= now:
            raise ValueError("scheduled_at must be in the future.")
        return v


class UpdateReminderRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = None
    reminder_type: ReminderType | None = None
    scheduled_at: datetime | None = None

    @field_validator("scheduled_at")
    @classmethod
    def must_be_future(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        from datetime import UTC

        now = datetime.now(UTC)
        if v.tzinfo is None:
            from datetime import timezone

            v = v.replace(tzinfo=timezone.utc)
        if v <= now:
            raise ValueError("scheduled_at must be in the future.")
        return v


class ReminderResponse(BaseModel):
    id: uuid.UUID
    gathering_id: uuid.UUID
    title: str
    body: str | None
    reminder_type: ReminderType
    scheduled_at: datetime
    is_sent: bool
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReminderListResponse(BaseModel):
    reminders: list[ReminderResponse]
    total: int
    pending: int   # not yet sent
    sent: int


# ---------------------------------------------------------------------------
# Safe dict conversion — avoids SQLAlchemy MissingGreenlet in async context
# ---------------------------------------------------------------------------


def _to_bool(v: object) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() == "true"
    return bool(v)


def reminder_to_dict(r: object) -> dict:
    return {
        "id": r.id,
        "gathering_id": r.gathering_id,
        "title": r.title,
        "body": r.body,
        "reminder_type": r.reminder_type,
        "scheduled_at": r.scheduled_at,
        "is_sent": _to_bool(r.is_sent),
        "sent_at": r.sent_at,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }
