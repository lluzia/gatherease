"""Unit tests for menu and dish endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

PASSWORD = "SecurePass1"


async def _setup(client: AsyncClient, email: str) -> tuple[str, str]:
    """Register, login, create gathering. Returns (token, gathering_id)."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    gathering = await client.post(
        "/api/v1/gatherings",
        json={
            "name": "Dinner Party",
            "event_date": "2026-08-01T19:00:00Z",
        },
        headers=auth,
    )
    return token, gathering.json()["id"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_empty_menu(client: AsyncClient):
    token, gid = await _setup(client, "menu1@test.com")
    resp = await client.get(f"/api/v1/gatherings/{gid}/menu", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["dishes"] == []


@pytest.mark.asyncio
async def test_add_dish(client: AsyncClient):
    token, gid = await _setup(client, "menu2@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "Caesar Salad", "category": "starter", "servings": 6},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Caesar Salad"
    assert data["category"] == "starter"
    assert data["servings"] == 6


@pytest.mark.asyncio
async def test_menu_shows_dishes(client: AsyncClient):
    token, gid = await _setup(client, "menu3@test.com")
    await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "Grilled Salmon", "category": "main"},
        headers=_auth(token),
    )
    await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "Tiramisu", "category": "dessert"},
        headers=_auth(token),
    )
    resp = await client.get(f"/api/v1/gatherings/{gid}/menu", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()["dishes"]) == 2


@pytest.mark.asyncio
async def test_update_dish(client: AsyncClient):
    token, gid = await _setup(client, "menu4@test.com")
    add = await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "Bruschetta", "category": "starter"},
        headers=_auth(token),
    )
    dish_id = add.json()["id"]

    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/menu/dishes/{dish_id}",
        json={"name": "Bruschetta al Pomodoro", "servings": 8},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Bruschetta al Pomodoro"
    assert resp.json()["servings"] == 8


@pytest.mark.asyncio
async def test_delete_dish(client: AsyncClient):
    token, gid = await _setup(client, "menu5@test.com")
    add = await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "Soup", "category": "starter"},
        headers=_auth(token),
    )
    dish_id = add.json()["id"]

    resp = await client.delete(
        f"/api/v1/gatherings/{gid}/menu/dishes/{dish_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 204

    menu = await client.get(f"/api/v1/gatherings/{gid}/menu", headers=_auth(token))
    assert len(menu.json()["dishes"]) == 0


@pytest.mark.asyncio
async def test_guest_page_shows_dishes(client: AsyncClient):
    """After adding dishes, the guest page should show their names."""
    token, gid = await _setup(client, "menu6@test.com")

    # Add dishes
    await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "Pasta", "category": "main"},
        headers=_auth(token),
    )

    # Generate invite
    invite = await client.post(f"/api/v1/gatherings/{gid}/invite", headers=_auth(token))
    inv_token = invite.json()["invite_token"]

    # Guest page should show dishes (show_menu=True by default)
    page = await client.get(f"/api/v1/i/{inv_token}")
    assert page.status_code == 200
    assert "Pasta" in page.json()["menu_dishes"]
