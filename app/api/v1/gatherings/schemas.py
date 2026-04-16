"""Pydantic schemas for gathering endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# ORM helper — safely converts a Gathering ORM object to a dict using only
# column values, avoiding lazy-load triggers on relationship attributes.
# ---------------------------------------------------------------------------


def gathering_to_dict(g: object) -> dict:
    """Extract scalar columns from a Gathering ORM object safely."""
    return {
        "id": g.id,
        "host_id": g.host_id,
        "name": g.name,
        "description": g.description,
        "location": g.location,
        "event_date": g.event_date,
        "guest_count_estimate": g.guest_count_estimate,
        "invite_token": g.invite_token,
        "show_menu": g.show_menu,
        "show_location": g.show_location,
        "show_shopping_list": g.show_shopping_list,
        "show_prep_tasks": g.show_prep_tasks,
        "is_archived": g.is_archived,
        "created_at": g.created_at,
        "updated_at": g.updated_at,
    }


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateGatheringRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=500)
    event_date: datetime
    guest_count_estimate: int = Field(default=0, ge=0, le=500)


class UpdateGatheringRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=500)
    event_date: datetime | None = None
    guest_count_estimate: int | None = Field(default=None, ge=0, le=500)
    # Visibility toggles for the guest public page
    show_menu: bool | None = None
    show_location: bool | None = None
    show_shopping_list: bool | None = None
    show_prep_tasks: bool | None = None
    is_archived: bool | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class GatheringResponse(BaseModel):
    id: uuid.UUID
    host_id: uuid.UUID
    name: str
    description: str | None
    location: str | None
    event_date: datetime
    guest_count_estimate: int
    invite_token: str | None
    show_menu: bool
    show_location: bool
    show_shopping_list: bool
    show_prep_tasks: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GatheringListResponse(BaseModel):
    gatherings: list[GatheringResponse]
    total: int


class InviteLinkResponse(BaseModel):
    invite_token: str
    invite_url: str


# ---------------------------------------------------------------------------
# Guest public page schemas (no auth required)
# ---------------------------------------------------------------------------


class GuestPageResponse(BaseModel):
    """What a guest sees when they open an invite link."""

    gathering_name: str
    event_date: datetime
    host_name: str | None
    location: str | None  # None if host hid it
    menu_dishes: list[str] | None  # dish names only, None if host hid menu


class RSVPRequest(BaseModel):
    guest_name: str = Field(min_length=1, max_length=255)
    guest_email: str | None = Field(default=None, max_length=320)
    status: str = Field(pattern=r"^(accepted|declined|maybe)$")
    message: str | None = Field(default=None, max_length=1000)


class RSVPResponse(BaseModel):
    id: uuid.UUID
    guest_name: str
    status: str
    message: str | None

    model_config = {"from_attributes": True}


class GuestListResponse(BaseModel):
    guests: list[RSVPResponse]
    total: int
    accepted: int
    declined: int
    maybe: int
    pending: int
