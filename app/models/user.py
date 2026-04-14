"""User model — maps to the `users` table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.gathering import Gathering


class User(BaseModel):
    __tablename__ = "users"

    # Cognito `sub` — authoritative user identifier from the identity provider
    cognito_sub: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_language: Mapped[str] = mapped_column(
        String(5), nullable=False, server_default="en"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True
    )
    is_premium: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    # Local auth only — None when using Cognito
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships (populated by Sprint 2 models)
    gatherings: Mapped[list[Gathering]] = relationship(
        "Gathering", back_populates="host", lazy="raise"
    )
