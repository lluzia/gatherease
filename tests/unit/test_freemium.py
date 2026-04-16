"""
Tests for freemium gating — free tier limited to 3 active gatherings.

Rules under test:
  - Free user: creating a 4th active gathering → 403 GATHERING_LIMIT_REACHED
  - Free user: deleting one of 3 → can create again (slot freed)
  - Free user: archiving one of 3 → can create again (archived ≠ active)
  - Premium user: can create beyond 3 with no error
  - Error message is translated per Accept-Language
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

PASSWORD = "SecurePass1!"
GATHERING = {"name": "Party", "event_date": "2026-12-01T19:00:00Z"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create(client: AsyncClient, token: str, name: str = "Party") -> dict:
    resp = await client.post(
        "/api/v1/gatherings",
        json={"name": name, "event_date": "2026-12-01T19:00:00Z"},
        headers=_auth(token),
    )
    return resp


async def _set_premium(db_session: AsyncSession, email: str, value: bool) -> None:
    """Directly flip is_premium on a user row — no endpoint exists for this yet."""
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.is_premium = value
    db_session.add(user)
    await db_session.flush()


# ---------------------------------------------------------------------------
# Free tier limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_user_can_create_three(client: AsyncClient) -> None:
    token = await _register_login(client, "free1@test.com")

    for i in range(3):
        resp = await _create(client, token, f"Party {i+1}")
        assert resp.status_code == 201, f"gathering {i+1} failed: {resp.text}"


@pytest.mark.asyncio
async def test_free_user_blocked_on_fourth(client: AsyncClient) -> None:
    token = await _register_login(client, "free2@test.com")

    for i in range(3):
        await _create(client, token, f"Party {i+1}")

    resp = await _create(client, token, "Party 4")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "GATHERING_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_free_user_blocked_fifth_after_extra_attempt(client: AsyncClient) -> None:
    """Repeated attempts beyond the limit all return 403."""
    token = await _register_login(client, "free3@test.com")

    for i in range(3):
        await _create(client, token, f"Party {i+1}")

    for _ in range(3):
        resp = await _create(client, token, "Extra")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Slot freed by delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_frees_slot(client: AsyncClient) -> None:
    token = await _register_login(client, "free4@test.com")

    ids = []
    for i in range(3):
        r = await _create(client, token, f"Party {i+1}")
        ids.append(r.json()["id"])

    # Blocked at 4
    assert (await _create(client, token, "Party 4")).status_code == 403

    # Delete one → slot opens
    await client.delete(f"/api/v1/gatherings/{ids[0]}", headers=_auth(token))

    resp = await _create(client, token, "Party 4 (retry)")
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Slot freed by archive (PATCH is_archived=true)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_frees_slot(client: AsyncClient) -> None:
    token = await _register_login(client, "free5@test.com")

    ids = []
    for i in range(3):
        r = await _create(client, token, f"Party {i+1}")
        ids.append(r.json()["id"])

    # Blocked at 4
    assert (await _create(client, token, "Party 4")).status_code == 403

    # Archive one → slot opens
    await client.patch(
        f"/api/v1/gatherings/{ids[0]}",
        json={"is_archived": True},
        headers=_auth(token),
    )

    resp = await _create(client, token, "Party 4 (retry)")
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Premium user — unlimited
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_premium_user_can_exceed_free_limit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = "premium1@test.com"
    token = await _register_login(client, email)
    await _set_premium(db_session, email, True)

    # Premium users can go well beyond 3
    for i in range(5):
        resp = await _create(client, token, f"VIP Party {i+1}")
        assert resp.status_code == 201, f"gathering {i+1} failed: {resp.text}"


@pytest.mark.asyncio
async def test_premium_to_free_downgrade_blocks_new(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """If premium lapses, existing gatherings are untouched but new ones are blocked."""
    email = "premium2@test.com"
    token = await _register_login(client, email)

    # Create 3 as free, upgrade, create 2 more
    for i in range(3):
        await _create(client, token, f"Party {i+1}")

    await _set_premium(db_session, email, True)

    for i in range(2):
        resp = await _create(client, token, f"Premium Party {i+1}")
        assert resp.status_code == 201

    # Downgrade back to free — 5 active gatherings, new ones blocked
    await _set_premium(db_session, email, False)

    resp = await _create(client, token, "Should fail")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "GATHERING_LIMIT_REACHED"


# ---------------------------------------------------------------------------
# i18n — limit error is translated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_limit_error_translated_pt(client: AsyncClient) -> None:
    token = await _register_login(client, "free6@test.com")

    for i in range(3):
        await _create(client, token, f"Party {i+1}")

    resp = await client.post(
        "/api/v1/gatherings",
        json=GATHERING,
        headers={**_auth(token), "Accept-Language": "pt"},
    )
    assert resp.status_code == 403
    assert "Premium" in resp.json()["error"]["message"]
    assert "Limite" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_limit_error_translated_es(client: AsyncClient) -> None:
    token = await _register_login(client, "free7@test.com")

    for i in range(3):
        await _create(client, token, f"Party {i+1}")

    resp = await client.post(
        "/api/v1/gatherings",
        json=GATHERING,
        headers={**_auth(token), "Accept-Language": "es"},
    )
    assert resp.status_code == 403
    assert "Premium" in resp.json()["error"]["message"]
    assert "Límite" in resp.json()["error"]["message"]


# ---------------------------------------------------------------------------
# Service constant
# ---------------------------------------------------------------------------


def test_free_limit_constant() -> None:
    from app.api.v1.gatherings.service import GatheringService
    assert GatheringService.FREE_GATHERING_LIMIT == 3
