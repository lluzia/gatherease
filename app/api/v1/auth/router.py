"""
Auth router — all endpoints under /api/v1/auth

POST /auth/register          – create account
POST /auth/login             – get tokens
POST /auth/refresh           – exchange refresh token
POST /auth/logout            – revoke tokens
POST /auth/forgot-password   – trigger reset email
POST /auth/reset-password    – confirm reset with code
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.v1.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.api.v1.auth.service import AuthService
from app.dependencies import DbSession

router = APIRouter(prefix="/auth", tags=["Authentication"])
_bearer = HTTPBearer()


def _get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    payload: RegisterRequest,
    service: AuthService = Depends(_get_auth_service),
) -> MessageResponse:
    result = await service.register(payload)
    return MessageResponse(**result)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT tokens",
)
async def login(
    payload: LoginRequest,
    service: AuthService = Depends(_get_auth_service),
) -> TokenResponse:
    return await service.login(payload)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh an access token",
)
async def refresh(
    payload: RefreshRequest,
    service: AuthService = Depends(_get_auth_service),
) -> TokenResponse:
    return await service.refresh(payload)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke tokens (global sign-out)",
)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    service: AuthService = Depends(_get_auth_service),
) -> MessageResponse:
    result = await service.logout(credentials.credentials)
    return MessageResponse(**result)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset email",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    service: AuthService = Depends(_get_auth_service),
) -> MessageResponse:
    result = await service.forgot_password(payload)
    return MessageResponse(**result)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Confirm password reset with code",
)
async def reset_password(
    payload: ResetPasswordRequest,
    service: AuthService = Depends(_get_auth_service),
) -> MessageResponse:
    result = await service.reset_password(payload)
    return MessageResponse(**result)
