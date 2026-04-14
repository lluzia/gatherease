"""Unit tests for shopping list endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

PASSWORD = "SecurePass1"


async def _setup(client: AsyncClient, email: str) -> tuple[str, str]:
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    gathering = await client.post(
        "/api/v1/gatherings",
        json={"name": "Party", "event_date": "2026-09-01T18:00:00Z"},
        headers=auth,
    )
    return token, gathering.json()["id"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_empty_shopping_list(client: AsyncClient):
    token, gid = await _setup(client, "shop1@test.com")
    resp = await client.get(f"/api/v1/gatherings/{gid}/shopping", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_add_item(client: AsyncClient):
    token, gid = await _setup(client, "shop2@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/shopping",
        json={"name": "Wine", "quantity": 3, "unit": "bottles", "assigned_to": "João"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Wine"
    assert data["quantity"] == 3.0
    assert data["unit"] == "bottles"
    assert data["is_purchased"] is False


@pytest.mark.asyncio
async def test_tick_item_as_purchased(client: AsyncClient):
    token, gid = await _setup(client, "shop3@test.com")
    add = await client.post(
        f"/api/v1/gatherings/{gid}/shopping",
        json={"name": "Bread"},
        headers=_auth(token),
    )
    item_id = add.json()["id"]

    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/shopping/{item_id}",
        json={"is_purchased": True},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_purchased"] is True

    # Check counts
    lst = await client.get(f"/api/v1/gatherings/{gid}/shopping", headers=_auth(token))
    assert lst.json()["purchased"] == 1
    assert lst.json()["remaining"] == 0


@pytest.mark.asyncio
async def test_delete_item(client: AsyncClient):
    token, gid = await _setup(client, "shop4@test.com")
    add = await client.post(
        f"/api/v1/gatherings/{gid}/shopping",
        json={"name": "Cheese"},
        headers=_auth(token),
    )
    item_id = add.json()["id"]

    resp = await client.delete(
        f"/api/v1/gatherings/{gid}/shopping/{item_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 204

    lst = await client.get(f"/api/v1/gatherings/{gid}/shopping", headers=_auth(token))
    assert lst.json()["total"] == 0
