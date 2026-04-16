"""
QA sweep — Auth & User profile edge cases.

Covers gaps not in test_auth.py:
  - Duplicate email registration → 409
  - Register with full_name and preferred_language stored correctly
  - Invalid email format → 422
  - Password missing uppercase → 422
  - Password missing digit → 422
  - Token refresh → new access token issued
  - Logout → 200
  - Reset password flow (local mode)
  - GET /users/me returns correct profile
  - PATCH /users/me — name, language, avatar
  - PATCH /users/me — invalid language code → 422
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

PASSWORD = "SecurePass1!"


async def _register(client: AsyncClient, email: str, **kwargs) -> dict:
    payload = {"email": email, "password": PASSWORD, **kwargs}
    resp = await client.post("/api/v1/auth/register", json=payload)
    return resp


async def _login(client: AsyncClient, email: str, password: str = PASSWORD) -> dict:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return resp


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    await _register(client, "dup@test.com")
    resp = await _register(client, "dup@test.com")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.asyncio
async def test_register_invalid_email_format(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": PASSWORD},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_uppercase(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "qa_pw1@test.com", "password": "alllowercase1"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_digit(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "qa_pw2@test.com", "password": "NoDigitsHere"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "qa_pw3@test.com", "password": "Ab1"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_stores_full_name_and_language(client: AsyncClient) -> None:
    await _register(
        client,
        "qa_profile1@test.com",
        full_name="João Silva",
        preferred_language="pt",
    )
    login = await _login(client, "qa_profile1@test.com")
    token = login.json()["access_token"]

    resp = await client.get("/api/v1/users/me", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "João Silva"
    assert data["preferred_language"] == "pt"


@pytest.mark.asyncio
async def test_register_invalid_language_code(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "qa_lang@test.com",
            "password": PASSWORD,
            "preferred_language": "fr",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient) -> None:
    resp = await _login(client, "nobody@test.com")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_returns_token_fields(client: AsyncClient) -> None:
    await _register(client, "qa_tok@test.com")
    resp = await _login(client, "qa_tok@test.com")
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_issues_new_access_token(client: AsyncClient) -> None:
    await _register(client, "qa_refresh1@test.com")
    login = await _login(client, "qa_refresh1@test.com")
    refresh_token = login.json()["refresh_token"]
    # original_access = login.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert resp.status_code == 200
    new_access = resp.json()["access_token"]
    # New access token is valid — use it
    me = await client.get("/api/v1/users/me", headers=_auth(new_access))
    assert me.status_code == 200


@pytest.mark.asyncio
async def test_refresh_with_invalid_token(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "garbage.token.here"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_returns_200(client: AsyncClient) -> None:
    await _register(client, "qa_logout@test.com")
    login = await _login(client, "qa_logout@test.com")
    token = login.json()["access_token"]

    resp = await client.post("/api/v1/auth/logout", headers=_auth(token))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Reset password (local mode)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_password_allows_login_with_new_password(
    client: AsyncClient,
) -> None:
    email = "qa_reset1@test.com"
    await _register(client, email)

    # Forgot password (always 200 in local mode)
    resp = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200

    # Reset (local mode accepts any code)
    new_pw = "NewPassword9!"
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"email": email, "confirmation_code": "000000", "new_password": new_pw},
    )
    assert resp.status_code == 200

    # Can now log in with new password
    login = await _login(client, email, password=new_pw)
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_nonexistent_email_still_200(
    client: AsyncClient,
) -> None:
    """Should not leak whether email exists."""
    resp = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "ghost@test.com"}
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_returns_profile(client: AsyncClient) -> None:
    await _register(client, "qa_me1@test.com", full_name="Test User")
    token = (await _login(client, "qa_me1@test.com")).json()["access_token"]

    resp = await client.get("/api/v1/users/me", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "qa_me1@test.com"
    assert data["full_name"] == "Test User"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_me_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_patch_me_updates_name(client: AsyncClient) -> None:
    await _register(client, "qa_me2@test.com")
    token = (await _login(client, "qa_me2@test.com")).json()["access_token"]

    resp = await client.patch(
        "/api/v1/users/me",
        json={"full_name": "Updated Name"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_patch_me_updates_language(client: AsyncClient) -> None:
    await _register(client, "qa_me3@test.com")
    token = (await _login(client, "qa_me3@test.com")).json()["access_token"]

    resp = await client.patch(
        "/api/v1/users/me",
        json={"preferred_language": "es"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["preferred_language"] == "es"


@pytest.mark.asyncio
async def test_patch_me_invalid_language_rejected(client: AsyncClient) -> None:
    await _register(client, "qa_me4@test.com")
    token = (await _login(client, "qa_me4@test.com")).json()["access_token"]

    resp = await client.patch(
        "/api/v1/users/me",
        json={"preferred_language": "de"},
        headers=_auth(token),
    )
    assert resp.status_code == 422
