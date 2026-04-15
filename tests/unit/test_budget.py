"""Unit tests for budget endpoints."""

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
    g = await client.post(
        "/api/v1/gatherings",
        json={"name": "Dinner", "event_date": "2026-10-01T19:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, g.json()["id"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_empty_budget(client: AsyncClient):
    token, gid = await _setup(client, "budget1@test.com")
    resp = await client.get(f"/api/v1/gatherings/{gid}/budget", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_spent"] == "0"
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_set_budget_limit(client: AsyncClient):
    token, gid = await _setup(client, "budget2@test.com")
    resp = await client.put(
        f"/api/v1/gatherings/{gid}/budget",
        json={"currency": "EUR", "host_budget_limit": "150.00"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["host_budget_limit"] == "150.00"
    assert data["host_remaining"] == "150.00"


@pytest.mark.asyncio
async def test_add_entry_updates_totals(client: AsyncClient):
    token, gid = await _setup(client, "budget3@test.com")
    await client.put(
        f"/api/v1/gatherings/{gid}/budget",
        json={"currency": "EUR", "host_budget_limit": "200.00"},
        headers=_auth(token),
    )
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/budget/entries",
        json={"description": "Wine bottles", "amount": "45.50", "paid_by": "Pedro"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["host_total_spent"] == "45.50"
    assert data["total_spent"] == "45.50"
    assert data["host_remaining"] == "154.50"
    assert len(data["entries"]) == 1


@pytest.mark.asyncio
async def test_delete_entry(client: AsyncClient):
    token, gid = await _setup(client, "budget4@test.com")
    add = await client.post(
        f"/api/v1/gatherings/{gid}/budget/entries",
        json={"description": "Cheese platter", "amount": "32.00"},
        headers=_auth(token),
    )
    entry_id = add.json()["entries"][0]["id"]

    resp = await client.delete(
        f"/api/v1/gatherings/{gid}/budget/entries/{entry_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["total_spent"] == "0"
    assert resp.json()["entries"] == []


@pytest.mark.asyncio
async def test_multiple_entries(client: AsyncClient):
    token, gid = await _setup(client, "budget5@test.com")
    await client.post(
        f"/api/v1/gatherings/{gid}/budget/entries",
        json={"description": "Meat", "amount": "60.00"},
        headers=_auth(token),
    )
    await client.post(
        f"/api/v1/gatherings/{gid}/budget/entries",
        json={"description": "Drinks", "amount": "40.00"},
        headers=_auth(token),
    )
    resp = await client.get(f"/api/v1/gatherings/{gid}/budget", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_spent"] == "100.00"
    assert len(data["entries"]) == 2
