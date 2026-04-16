"""Pydantic schemas for user profile endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    preferred_language: str
    is_premium: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None)
    preferred_language: str | None = Field(default=None, pattern=r"^(en|pt|es)$")


class DeviceTokenRequest(BaseModel):
    fcm_token: str | None = Field(
        default=None,
        max_length=512,
        description="FCM device token from Flutter firebase_messaging package. "
        "Pass null to clear the token (e.g. on logout).",
    )
