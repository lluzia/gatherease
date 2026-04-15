"""Schemas for prep task endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AddPrepTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    assigned_to: str | None = Field(default=None, max_length=255)
    due_at: datetime | None = None
    sort_order: int = Field(default=0, ge=0)


class UpdatePrepTaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    assigned_to: str | None = None
    due_at: datetime | None = None
    is_completed: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)


class PrepTaskResponse(BaseModel):
    id: uuid.UUID
    gathering_id: uuid.UUID
    title: str
    description: str | None
    assigned_to: str | None
    due_at: datetime | None
    is_completed: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class PrepTaskListResponse(BaseModel):
    tasks: list[PrepTaskResponse]
    total: int
    completed: int
    remaining: int


def _to_bool(v: object) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() == "true"
    return bool(v)


def task_to_dict(t: object) -> dict:
    return {
        "id": t.id,
        "gathering_id": t.gathering_id,
        "title": t.title,
        "description": t.description,
        "assigned_to": t.assigned_to,
        "due_at": t.due_at,
        "is_completed": _to_bool(t.is_completed),
        "sort_order": t.sort_order,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }
