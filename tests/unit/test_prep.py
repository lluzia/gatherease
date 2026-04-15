"""Unit tests for prep task endpoints."""

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
        json={"name": "Party", "event_date": "2026-09-01T18:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, g.json()["id"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_empty_prep_list(client: AsyncClient):
    token, gid = await _setup(client, "prep1@test.com")
    resp = await client.get(f"/api/v1/gatherings/{gid}/prep", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_add_prep_task(client: AsyncClient):
    token, gid = await _setup(client, "prep2@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/prep",
        json={"title": "Marinate the chicken", "assigned_to": "Pedro"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Marinate the chicken"
    assert resp.json()["is_completed"] is False


@pytest.mark.asyncio
async def test_complete_task(client: AsyncClient):
    token, gid = await _setup(client, "prep3@test.com")
    add = await client.post(
        f"/api/v1/gatherings/{gid}/prep",
        json={"title": "Set the table"},
        headers=_auth(token),
    )
    tid = add.json()["id"]
    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/prep/{tid}",
        json={"is_completed": True},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_completed"] is True

    lst = await client.get(f"/api/v1/gatherings/{gid}/prep", headers=_auth(token))
    assert lst.json()["completed"] == 1
    assert lst.json()["remaining"] == 0


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient):
    token, gid = await _setup(client, "prep4@test.com")
    add = await client.post(
        f"/api/v1/gatherings/{gid}/prep",
        json={"title": "Buy ice"},
        headers=_auth(token),
    )
    tid = add.json()["id"]
    resp = await client.delete(
        f"/api/v1/gatherings/{gid}/prep/{tid}", headers=_auth(token)
    )
    assert resp.status_code == 204
    lst = await client.get(f"/api/v1/gatherings/{gid}/prep", headers=_auth(token))
    assert lst.json()["total"] == 0
