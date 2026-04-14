"""
Users router — /api/v1/users

GET  /users/me    – return authenticated user profile
PATCH /users/me   – update profile fields
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.users.schemas import UpdateProfileRequest, UserResponse
from app.api.v1.users.service import UserService
from app.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/users", tags=["Users"])


def _get_user_service(db: DbSession) -> UserService:
    return UserService(db)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get authenticated user profile",
)
async def get_me(
    current_user: CurrentUser,
    service: UserService = Depends(_get_user_service),
) -> UserResponse:
    user = await service.get_me(current_user)
    return UserResponse.model_validate(user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update authenticated user profile",
)
async def update_me(
    payload: UpdateProfileRequest,
    current_user: CurrentUser,
    service: UserService = Depends(_get_user_service),
) -> UserResponse:
    user = await service.update_me(current_user, payload)
    return UserResponse.model_validate(user)
