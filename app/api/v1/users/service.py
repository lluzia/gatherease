"""User profile service."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.users.schemas import UpdateProfileRequest
from app.models.user import User


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_me(self, user: User) -> User:
        return user

    async def update_me(self, user: User, payload: UpdateProfileRequest) -> User:
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.avatar_url is not None:
            user.avatar_url = payload.avatar_url
        if payload.preferred_language is not None:
            user.preferred_language = payload.preferred_language
        self._db.add(user)
        await self._db.flush()
        return user
