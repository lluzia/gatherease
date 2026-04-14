"""Unit tests for gathering endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

TEST_EMAIL = "host@gatherease.app"
TEST_PASSWORD = "SecurePass1"


async def _get_token(client: AsyncClient) -> str:
    """Register + login, return access token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


GATHERING_PAYLOAD = {
    "name": "Summer BBQ",
    "description": "Backyard party",
    "location": "My house",
    "event_date": "2026-07-15T18:00:00Z",
    "guest_count_estimate": 10,
}


@pytest.mark.asyncio
async def test_create_gathering(client: AsyncClient):
    token = await _get_token(client)
    resp = await client.post(
        "/api/v1/gatherings", json=GATHERING_PAYLOAD, headers=_auth(token)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Summer BBQ"
    assert data["location"] == "My house"
    assert data["invite_token"] is None  # not generated yet


@pytest.mark.asyncio
async def test_list_gatherings(client: AsyncClient):
    token = await _get_token(client)
    await client.post(
        "/api/v1/gatherings", json=GATHERING_PAYLOAD, headers=_auth(token)
    )
    resp = await client.get("/api/v1/gatherings", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_update_gathering(client: AsyncClient):
    token = await _get_token(client)
    create = await client.post(
        "/api/v1/gatherings", json=GATHERING_PAYLOAD, headers=_auth(token)
    )
    gid = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/gatherings/{gid}",
        json={"name": "Updated BBQ", "show_location": False},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated BBQ"
    assert resp.json()["show_location"] is False


@pytest.mark.asyncio
async def test_delete_gathering(client: AsyncClient):
    token = await _get_token(client)
    create = await client.post(
        "/api/v1/gatherings", json=GATHERING_PAYLOAD, headers=_auth(token)
    )
    gid = create.json()["id"]

    resp = await client.delete(f"/api/v1/gatherings/{gid}", headers=_auth(token))
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/gatherings/{gid}", headers=_auth(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invite_and_rsvp(client: AsyncClient):
    token = await _get_token(client)

    # Create gathering
    create = await client.post(
        "/api/v1/gatherings", json=GATHERING_PAYLOAD, headers=_auth(token)
    )
    gid = create.json()["id"]

    # Generate invite
    invite = await client.post(f"/api/v1/gatherings/{gid}/invite", headers=_auth(token))
    assert invite.status_code == 200
    invite_token = invite.json()["invite_token"]
    assert invite_token is not None

    # Guest views public page
    page = await client.get(f"/api/v1/i/{invite_token}")
    assert page.status_code == 200
    assert page.json()["gathering_name"] == "Summer BBQ"

    # Guest submits RSVP (no auth)
    rsvp = await client.post(
        f"/api/v1/i/{invite_token}/rsvp",
        json={
            "guest_name": "Maria",
            "guest_email": "maria@test.com",
            "status": "accepted",
            "message": "Can't wait!",
        },
    )
    assert rsvp.status_code == 201
    assert rsvp.json()["status"] == "accepted"

    # Host sees guest list
    guests = await client.get(f"/api/v1/gatherings/{gid}/guests", headers=_auth(token))
    assert guests.status_code == 200
    data = guests.json()
    assert data["total"] == 1
    assert data["accepted"] == 1
    assert data["guests"][0]["guest_name"] == "Maria"


@pytest.mark.asyncio
async def test_forbidden_for_non_host(client: AsyncClient):
    """A user cannot access another user's gathering."""
    token1 = await _get_token(client)
    create = await client.post(
        "/api/v1/gatherings", json=GATHERING_PAYLOAD, headers=_auth(token1)
    )
    gid = create.json()["id"]

    # Register a second user
    await client.post(
        "/api/v1/auth/register",
        json={"email": "other@test.com", "password": TEST_PASSWORD},
    )
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": "other@test.com", "password": TEST_PASSWORD},
    )
    token2 = login2.json()["access_token"]

    resp = await client.get(f"/api/v1/gatherings/{gid}", headers=_auth(token2))
    assert resp.status_code == 403
