"""Unit tests for auth endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# Email used consistently across tests that depend on each other
TEST_EMAIL = "testuser@gatherease.app"
TEST_PASSWORD = "SecurePass1"


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": "Test User",
            "preferred_language": "en",
        },
    )
    assert response.status_code == 201
    assert "message" in response.json()


@pytest.mark.asyncio
async def test_register_invalid_password(client: AsyncClient):
    """Password without uppercase should fail validation."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "x@test.com", "password": "alllowercase1"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Register then login — local auth mode requires the user to exist in DB."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "logintest@gatherease.app", "password": TEST_PASSWORD},
    )
    # Now login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "logintest@gatherease.app", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Login with wrong password should return 401."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpass@gatherease.app", "password": TEST_PASSWORD},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@gatherease.app", "password": "WrongPass1"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_forgot_password_always_200(client: AsyncClient):
    """Forgot-password must not reveal whether email exists."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@gatherease.app"},
    )
    assert response.status_code == 200
    assert "message" in response.json()
