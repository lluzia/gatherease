"""
QA sweep — Gatherings, invites, RSVP edge cases.

Covers gaps not in test_gatherings.py:
  - GET non-existent gathering → 404
  - Archived gatherings excluded from list
  - Visibility toggles: location hidden, menu hidden on guest page
  - RSVP declined and maybe statuses
  - Duplicate invite generation is idempotent (same token)
  - Guest list counts per status
  - RSVP with no email (optional field)
  - Invalid RSVP status → 422
  - Guest page 404 for bad token
  - Create gathering — name max length validation
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

PASSWORD = "SecurePass1!"


async def _register_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_gathering(client: AsyncClient, token: str, **kwargs) -> dict:
    payload = {"name": "QA Party", "event_date": "2026-12-01T19:00:00Z", **kwargs}
    resp = await client.post("/api/v1/gatherings", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _get_invite_token(client: AsyncClient, token: str, gid: str) -> str:
    resp = await client.post(f"/api/v1/gatherings/{gid}/invite", headers=_auth(token))
    assert resp.status_code == 200
    return resp.json()["invite_token"]


# ---------------------------------------------------------------------------
# CRUD edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_nonexistent_gathering_404(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g1@test.com")
    resp = await client.get(
        f"/api/v1/gatherings/{uuid.uuid4()}", headers=_auth(token)
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "GATHERING_NOT_FOUND"


@pytest.mark.asyncio
async def test_archived_gatherings_excluded_from_list(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g2@test.com")
    g1 = await _create_gathering(client, token, name="Active")
    g2 = await _create_gathering(client, token, name="To Archive")

    # Archive g2
    await client.patch(
        f"/api/v1/gatherings/{g2['id']}",
        json={"is_archived": True},
        headers=_auth(token),
    )

    resp = await client.get("/api/v1/gatherings", headers=_auth(token))
    ids = [g["id"] for g in resp.json()["gatherings"]]
    assert g1["id"] in ids
    assert g2["id"] not in ids


@pytest.mark.asyncio
async def test_create_gathering_name_too_long(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g3@test.com")
    resp = await client.post(
        "/api/v1/gatherings",
        json={"name": "x" * 256, "event_date": "2026-12-01T19:00:00Z"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_gathering_name_empty_rejected(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g4@test.com")
    resp = await client.post(
        "/api/v1/gatherings",
        json={"name": "", "event_date": "2026-12-01T19:00:00Z"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_nonexistent_gathering_404(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g5@test.com")
    resp = await client.patch(
        f"/api/v1/gatherings/{uuid.uuid4()}",
        json={"name": "Ghost"},
        headers=_auth(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_gathering_404(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g6@test.com")
    resp = await client.delete(
        f"/api/v1/gatherings/{uuid.uuid4()}", headers=_auth(token)
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Visibility toggles on guest page
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guest_page_hides_location_when_toggled(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g7@test.com")
    g = await _create_gathering(client, token, location="Secret Venue")

    # Hide location
    await client.patch(
        f"/api/v1/gatherings/{g['id']}",
        json={"show_location": False},
        headers=_auth(token),
    )

    invite_token = await _get_invite_token(client, token, g["id"])
    page = await client.get(f"/api/v1/i/{invite_token}")
    assert page.status_code == 200
    assert page.json()["location"] is None


@pytest.mark.asyncio
async def test_guest_page_shows_location_by_default(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g8@test.com")
    g = await _create_gathering(client, token, location="Public Venue")
    invite_token = await _get_invite_token(client, token, g["id"])

    page = await client.get(f"/api/v1/i/{invite_token}")
    assert page.status_code == 200
    assert page.json()["location"] == "Public Venue"


@pytest.mark.asyncio
async def test_guest_page_invalid_token_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/i/nonexistent-token-xyz")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Invite idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_invite_idempotent(client: AsyncClient) -> None:
    """Calling /invite twice returns the same token."""
    token = await _register_login(client, "qa_g9@test.com")
    g = await _create_gathering(client, token)

    r1 = await client.post(f"/api/v1/gatherings/{g['id']}/invite", headers=_auth(token))
    r2 = await client.post(f"/api/v1/gatherings/{g['id']}/invite", headers=_auth(token))

    assert r1.json()["invite_token"] == r2.json()["invite_token"]


# ---------------------------------------------------------------------------
# RSVP statuses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rsvp_declined(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g10@test.com")
    g = await _create_gathering(client, token)
    invite_token = await _get_invite_token(client, token, g["id"])

    resp = await client.post(
        f"/api/v1/i/{invite_token}/rsvp",
        json={"guest_name": "Pedro", "status": "declined"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "declined"


@pytest.mark.asyncio
async def test_rsvp_maybe(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g11@test.com")
    g = await _create_gathering(client, token)
    invite_token = await _get_invite_token(client, token, g["id"])

    resp = await client.post(
        f"/api/v1/i/{invite_token}/rsvp",
        json={"guest_name": "Ana", "status": "maybe"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "maybe"


@pytest.mark.asyncio
async def test_rsvp_without_email(client: AsyncClient) -> None:
    """Email is optional on RSVP."""
    token = await _register_login(client, "qa_g12@test.com")
    g = await _create_gathering(client, token)
    invite_token = await _get_invite_token(client, token, g["id"])

    resp = await client.post(
        f"/api/v1/i/{invite_token}/rsvp",
        json={"guest_name": "Anonymous", "status": "accepted"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_rsvp_invalid_status_rejected(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g13@test.com")
    g = await _create_gathering(client, token)
    invite_token = await _get_invite_token(client, token, g["id"])

    resp = await client.post(
        f"/api/v1/i/{invite_token}/rsvp",
        json={"guest_name": "X", "status": "attending"},  # invalid
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Guest list counts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guest_list_counts_by_status(client: AsyncClient) -> None:
    token = await _register_login(client, "qa_g14@test.com")
    g = await _create_gathering(client, token)
    invite_token = await _get_invite_token(client, token, g["id"])

    for name, status in [("A", "accepted"), ("B", "accepted"), ("C", "declined"), ("D", "maybe")]:
        await client.post(
            f"/api/v1/i/{invite_token}/rsvp",
            json={"guest_name": name, "status": status},
        )

    guests = await client.get(
        f"/api/v1/gatherings/{g['id']}/guests", headers=_auth(token)
    )
    data = guests.json()
    assert data["total"] == 4
    assert data["accepted"] == 2
    assert data["declined"] == 1
    assert data["maybe"] == 1
