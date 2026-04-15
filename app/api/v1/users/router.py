"""
Users router — /api/v1/users

GET   /users/me               – return authenticated user profile
PATCH /users/me               – update profile fields
PATCH /users/me/device-token  – register/clear FCM push token
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.users.schemas import DeviceTokenRequest, UpdateProfileRequest, UserResponse
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

@router.patch(
    "/me/device-token",
    response_model=UserResponse,
    summary="Register or clear FCM device token",
    description=(
        "Called by Flutter after firebase_messaging.getToken() resolves. "
        "Pass fcm_token: null to clear the token on logout, so stale tokens "
        "are not targeted by reminder dispatches."
    ),
)
async def register_device_token(
    payload: DeviceTokenRequest,
    current_user: CurrentUser,
    service: UserService = Depends(_get_user_service),
) -> UserResponse:
    user = await service.register_device_token(current_user, payload.fcm_token)
    return UserResponse.model_validate(user)
