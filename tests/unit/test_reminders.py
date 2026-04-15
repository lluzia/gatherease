"""
Unit tests for the reminders endpoints.

Covers:
  - CRUD (list, create, update, delete)
  - Validation (past scheduled_at, modifying sent reminder)
  - Host-only access enforcement
  - Manual dispatch (/send) + SNS publish assertion
  - Device token registration (PATCH /users/me/device-token)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

PASSWORD = "SecurePass1!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_gathering(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/api/v1/gatherings",
        json={"name": "Reminder Party", "event_date": "2026-12-25T19:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _future(minutes: int = 60) -> str:
    """ISO string that is `minutes` from now."""
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


def _past(minutes: int = 5) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


async def _create_reminder(
    client: AsyncClient,
    token: str,
    gid: str,
    *,
    title: str = "Test Reminder",
    minutes: int = 60,
    reminder_type: str = "push",
) -> dict:
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/reminders",
        json={
            "title": title,
            "body": "Don't forget!",
            "reminder_type": reminder_type,
            "scheduled_at": _future(minutes),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_reminders_empty(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_list1@test.com")
    gid = await _create_gathering(client, token)

    resp = await client.get(f"/api/v1/gatherings/{gid}/reminders", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["reminders"] == []
    assert data["total"] == 0
    assert data["pending"] == 0
    assert data["sent"] == 0


@pytest.mark.asyncio
async def test_list_reminders_counts(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_list2@test.com")
    gid = await _create_gathering(client, token)

    await _create_reminder(client, token, gid, title="R1")
    await _create_reminder(client, token, gid, title="R2")

    resp = await client.get(f"/api/v1/gatherings/{gid}/reminders", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["pending"] == 2
    assert data["sent"] == 0


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_reminder_push(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_create1@test.com")
    gid = await _create_gathering(client, token)

    resp = await client.post(
        f"/api/v1/gatherings/{gid}/reminders",
        json={
            "title": "Bring wine",
            "body": "Pick up two bottles",
            "reminder_type": "push",
            "scheduled_at": _future(120),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Bring wine"
    assert data["body"] == "Pick up two bottles"
    assert data["reminder_type"] == "push"
    assert data["is_sent"] is False
    assert data["sent_at"] is None
    assert "id" in data


@pytest.mark.asyncio
async def test_create_reminder_email_type(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_create2@test.com")
    gid = await _create_gathering(client, token)

    r = await _create_reminder(client, token, gid, reminder_type="email")
    assert r["reminder_type"] == "email"


@pytest.mark.asyncio
async def test_create_reminder_both_type(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_create3@test.com")
    gid = await _create_gathering(client, token)

    r = await _create_reminder(client, token, gid, reminder_type="both")
    assert r["reminder_type"] == "both"


@pytest.mark.asyncio
async def test_create_reminder_past_date_rejected(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_create4@test.com")
    gid = await _create_gathering(client, token)

    resp = await client.post(
        f"/api/v1/gatherings/{gid}/reminders",
        json={
            "title": "Too late",
            "reminder_type": "push",
            "scheduled_at": _past(10),
        },
        headers=_auth(token),
    )
    # Pydantic validator rejects past dates
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_reminder_requires_auth(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_create5@test.com")
    gid = await _create_gathering(client, token)

    resp = await client.post(
        f"/api/v1/gatherings/{gid}/reminders",
        json={"title": "X", "reminder_type": "push", "scheduled_at": _future()},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_reminder_non_host_forbidden(client: AsyncClient) -> None:
    host_token = await _register_login(client, "rem_host1@test.com")
    other_token = await _register_login(client, "rem_other1@test.com")
    gid = await _create_gathering(client, host_token)

    resp = await client.post(
        f"/api/v1/gatherings/{gid}/reminders",
        json={"title": "X", "reminder_type": "push", "scheduled_at": _future()},
        headers=_auth(other_token),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_reminder_title(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_upd1@test.com")
    gid = await _create_gathering(client, token)
    r = await _create_reminder(client, token, gid)

    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/reminders/{r['id']}",
        json={"title": "Updated title"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated title"


@pytest.mark.asyncio
async def test_update_reminder_type(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_upd2@test.com")
    gid = await _create_gathering(client, token)
    r = await _create_reminder(client, token, gid, reminder_type="push")

    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/reminders/{r['id']}",
        json={"reminder_type": "email"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["reminder_type"] == "email"


@pytest.mark.asyncio
async def test_update_reminder_past_date_rejected(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_upd3@test.com")
    gid = await _create_gathering(client, token)
    r = await _create_reminder(client, token, gid)

    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/reminders/{r['id']}",
        json={"scheduled_at": _past()},
        headers=_auth(token),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_reminder(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_del1@test.com")
    gid = await _create_gathering(client, token)
    r = await _create_reminder(client, token, gid)

    resp = await client.delete(
        f"/api/v1/gatherings/{gid}/reminders/{r['id']}",
        headers=_auth(token),
    )
    assert resp.status_code == 204

    # Confirm it's gone from the list
    list_resp = await client.get(
        f"/api/v1/gatherings/{gid}/reminders", headers=_auth(token)
    )
    assert list_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_reminder_non_host_forbidden(client: AsyncClient) -> None:
    host_token = await _register_login(client, "rem_del2@test.com")
    other_token = await _register_login(client, "rem_del3@test.com")
    gid = await _create_gathering(client, host_token)
    r = await _create_reminder(client, host_token, gid)

    resp = await client.delete(
        f"/api/v1/gatherings/{gid}/reminders/{r['id']}",
        headers=_auth(other_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_reminder_not_found(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_del4@test.com")
    gid = await _create_gathering(client, token)

    import uuid
    resp = await client.delete(
        f"/api/v1/gatherings/{gid}/reminders/{uuid.uuid4()}",
        headers=_auth(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Dispatch (/send)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_reminder_marks_sent(client: AsyncClient, mock_sns) -> None:
    token = await _register_login(client, "rem_send1@test.com")
    gid = await _create_gathering(client, token)
    r = await _create_reminder(client, token, gid)

    # mock_sns patches publish_event (sync); publish_reminder_fire calls it via await
    # We need it to be an async no-op
    with patch("app.services.sns.publish_event", new_callable=AsyncMock) as async_sns:
        async_sns.return_value = None
        resp = await client.post(
            f"/api/v1/gatherings/{gid}/reminders/{r['id']}/send",
            headers=_auth(token),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_sent"] is True
    assert data["sent_at"] is not None


@pytest.mark.asyncio
async def test_send_reminder_publishes_sns(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_send2@test.com")
    gid = await _create_gathering(client, token)
    r = await _create_reminder(client, token, gid, title="SNS Check")

    with patch("app.services.sns.publish_event", new_callable=AsyncMock) as async_sns:
        async_sns.return_value = None
        resp = await client.post(
            f"/api/v1/gatherings/{gid}/reminders/{r['id']}/send",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        # SNS publish_event was called once with event type reminder.fire
        async_sns.assert_called_once()
        call_args = async_sns.call_args
        assert call_args[0][0] == "reminder.fire"
        payload = call_args[0][1]
        assert payload["title"] == "SNS Check"
        assert payload["gathering_id"] == gid


@pytest.mark.asyncio
async def test_send_reminder_twice_returns_400(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_send3@test.com")
    gid = await _create_gathering(client, token)
    r = await _create_reminder(client, token, gid)

    with patch("app.services.sns.publish_event", new_callable=AsyncMock):
        await client.post(
            f"/api/v1/gatherings/{gid}/reminders/{r['id']}/send",
            headers=_auth(token),
        )
        # Second call should be rejected
        resp = await client.post(
            f"/api/v1/gatherings/{gid}/reminders/{r['id']}/send",
            headers=_auth(token),
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cannot_update_sent_reminder(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_send4@test.com")
    gid = await _create_gathering(client, token)
    r = await _create_reminder(client, token, gid)

    with patch("app.services.sns.publish_event", new_callable=AsyncMock):
        await client.post(
            f"/api/v1/gatherings/{gid}/reminders/{r['id']}/send",
            headers=_auth(token),
        )

    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/reminders/{r['id']}",
        json={"title": "Too late to change"},
        headers=_auth(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_send_includes_fcm_token_when_set(client: AsyncClient) -> None:
    """If the host has an FCM token registered, it appears in the SNS payload."""
    token = await _register_login(client, "rem_fcm1@test.com")
    gid = await _create_gathering(client, token)

    # Register a device token first
    await client.patch(
        "/api/v1/users/me/device-token",
        json={"fcm_token": "fake-fcm-token-abc123"},
        headers=_auth(token),
    )

    r = await _create_reminder(client, token, gid, title="FCM Test")

    with patch("app.services.sns.publish_event", new_callable=AsyncMock) as async_sns:
        async_sns.return_value = None
        resp = await client.post(
            f"/api/v1/gatherings/{gid}/reminders/{r['id']}/send",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        payload = async_sns.call_args[0][1]
        assert payload["fcm_token"] == "fake-fcm-token-abc123"


# ---------------------------------------------------------------------------
# Device token endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_device_token(client: AsyncClient) -> None:
    token = await _register_login(client, "devtoken1@test.com")

    resp = await client.patch(
        "/api/v1/users/me/device-token",
        json={"fcm_token": "fcm_token_xyz_789"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    # UserResponse doesn't expose fcm_token (it's internal) but the call succeeds


@pytest.mark.asyncio
async def test_clear_device_token(client: AsyncClient) -> None:
    token = await _register_login(client, "devtoken2@test.com")

    # Set then clear
    await client.patch(
        "/api/v1/users/me/device-token",
        json={"fcm_token": "some-token"},
        headers=_auth(token),
    )
    resp = await client.patch(
        "/api/v1/users/me/device-token",
        json={"fcm_token": None},
        headers=_auth(token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_device_token_requires_auth(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/users/me/device-token",
        json={"fcm_token": "token"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List ordering — reminders returned sorted by scheduled_at ascending
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reminders_sorted_by_scheduled_at(client: AsyncClient) -> None:
    token = await _register_login(client, "rem_sort1@test.com")
    gid = await _create_gathering(client, token)

    # Create in reverse chronological order
    await _create_reminder(client, token, gid, title="Later", minutes=120)
    await _create_reminder(client, token, gid, title="Sooner", minutes=30)

    resp = await client.get(
        f"/api/v1/gatherings/{gid}/reminders", headers=_auth(token)
    )
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()["reminders"]]
    assert titles == ["Sooner", "Later"]
