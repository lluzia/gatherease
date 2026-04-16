"""
Integration tests for the budget WebSocket endpoint.

WS path: ws://host/ws/gatherings/{id}/budget?token=<jwt>
         (note: no /api/v1 prefix — ws_router is mounted at app root)

Tests cover:
  - Successful connection + immediate state push on connect
  - Ping/pong keepalive
  - Broadcast to all connected clients when a REST mutation fires
  - Reject missing token (close code 4001)
  - Reject invalid token (close code 4001)
  - Reject expired token (close code 4002)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt
from starlette.testclient import TestClient

PASSWORD = "SecurePass1!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """Register a user and return a valid access token."""
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_gathering(client: AsyncClient, token: str) -> str:
    """Create a gathering and return its ID."""
    resp = await client.post(
        "/api/v1/gatherings",
        json={"name": "WS Test Gathering", "event_date": "2026-12-01T19:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _expired_token(
    secret: str = "test-secret-key-not-for-production",  # noqa: S107
) -> str:  # noqa: S107
    """Build a structurally valid JWT that is already expired."""
    now = datetime.now(UTC)
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "type": "access",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
        "iss": "gatherease-local",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _invalid_token() -> str:
    return "this.is.not.a.valid.jwt"


def _ws_url(gathering_id: str, token: str | None = None) -> str:
    base = f"/ws/gatherings/{gathering_id}/budget"
    return f"{base}?token={token}" if token else base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ws_rejects_missing_token(app, client: AsyncClient) -> None:
    """WS must close with 4001 when no ?token is provided."""
    import pytest
    from starlette.websockets import WebSocketDisconnect

    token = await _register_and_login(client, "wsreject1@test.com")
    gid = await _create_gathering(client, token)

    sync_client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with sync_client.websocket_connect(_ws_url(gid)) as ws:
            ws.receive_text()  # blocks until server closes
    assert exc_info.value.code == 4001


@pytest.mark.asyncio
async def test_ws_rejects_invalid_token(app, client: AsyncClient) -> None:
    """WS must close with 4001 when the token is malformed."""
    import pytest
    from starlette.websockets import WebSocketDisconnect

    token = await _register_and_login(client, "wsreject2@test.com")
    gid = await _create_gathering(client, token)

    sync_client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with sync_client.websocket_connect(_ws_url(gid, _invalid_token())) as ws:
            ws.receive_text()
    assert exc_info.value.code == 4001


@pytest.mark.asyncio
async def test_ws_rejects_expired_token(app, client: AsyncClient) -> None:
    """WS must close with 4002 when the token is expired."""
    import pytest
    from starlette.websockets import WebSocketDisconnect

    token = await _register_and_login(client, "wsreject3@test.com")
    gid = await _create_gathering(client, token)

    sync_client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with sync_client.websocket_connect(_ws_url(gid, _expired_token())) as ws:
            ws.receive_text()
    assert exc_info.value.code == 4002


@pytest.mark.asyncio
async def test_ws_connects_with_valid_token(app, client: AsyncClient) -> None:
    """
    A valid token → connection is accepted.
    When no budget exists yet the server sends nothing on connect
    (the initial-state push is skipped for a gathering with no Budget row).
    Ping → pong round-trip proves the connection is alive.
    """
    token = await _register_and_login(client, "wsok1@test.com")
    gid = await _create_gathering(client, token)

    sync_client = TestClient(app)
    with sync_client.websocket_connect(_ws_url(gid, token)) as ws:
        # No budget row yet — server won't push anything, send a ping
        ws.send_text("ping")
        reply = ws.receive_text()
        assert reply == "pong"


@pytest.mark.asyncio
async def test_ws_sends_initial_state_when_budget_exists(
    app, client: AsyncClient
) -> None:
    """
    After a budget limit has been SET via REST, a freshly-connected WS client
    should receive the current state immediately on connect (no poll needed).
    """
    token = await _register_and_login(client, "wsok2@test.com")
    gid = await _create_gathering(client, token)

    # Set a budget limit first
    resp = await client.put(
        f"/api/v1/gatherings/{gid}/budget",
        json={"currency": "EUR", "host_budget_limit": "250.00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    sync_client = TestClient(app)
    with sync_client.websocket_connect(_ws_url(gid, token)) as ws:
        # Should immediately receive the current budget state
        raw = ws.receive_text()
        data = json.loads(raw)
        assert data["host_budget_limit"] == "250.00"
        assert data["total_spent"] == "0"
        assert data["entries"] == []


@pytest.mark.asyncio
async def test_ws_receives_broadcast_on_entry_added(app, client: AsyncClient) -> None:
    """
    When a REST caller POSTs a budget entry, the WS client connected to that
    gathering should receive the updated BudgetResponse as a broadcast.
    """
    token = await _register_and_login(client, "wsok3@test.com")
    gid = await _create_gathering(client, token)

    # Set a limit so entries make sense
    await client.put(
        f"/api/v1/gatherings/{gid}/budget",
        json={"currency": "EUR", "host_budget_limit": "500.00"},
        headers={"Authorization": f"Bearer {token}"},
    )

    sync_client = TestClient(app)
    with sync_client.websocket_connect(_ws_url(gid, token)) as ws:
        # Consume the initial state push
        ws.receive_text()

        # Trigger a REST mutation — this should broadcast to the WS
        resp = await client.post(
            f"/api/v1/gatherings/{gid}/budget/entries",
            json={"description": "Wine", "amount": "35.50"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201

        # WS should receive the broadcast
        raw = ws.receive_text()
        data = json.loads(raw)
        assert data["total_spent"] == "35.50"
        assert len(data["entries"]) == 1
        assert data["entries"][0]["description"] == "Wine"


@pytest.mark.asyncio
async def test_ws_broadcast_on_entry_deleted(app, client: AsyncClient) -> None:
    """Deleting an entry via REST also broadcasts the updated state to WS clients."""
    token = await _register_and_login(client, "wsok4@test.com")
    gid = await _create_gathering(client, token)

    await client.put(
        f"/api/v1/gatherings/{gid}/budget",
        json={"currency": "EUR", "host_budget_limit": "300.00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    add_resp = await client.post(
        f"/api/v1/gatherings/{gid}/budget/entries",
        json={"description": "Cheese", "amount": "22.00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert add_resp.status_code == 201
    entry_id = add_resp.json()["entries"][0]["id"]

    sync_client = TestClient(app)
    with sync_client.websocket_connect(_ws_url(gid, token)) as ws:
        # Initial state push (one entry exists)
        initial = json.loads(ws.receive_text())
        assert len(initial["entries"]) == 1

        # Delete the entry
        del_resp = await client.delete(
            f"/api/v1/gatherings/{gid}/budget/entries/{entry_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert del_resp.status_code == 200

        # Broadcast received — entries should now be empty
        updated = json.loads(ws.receive_text())
        assert updated["entries"] == []
        assert updated["total_spent"] == "0"


@pytest.mark.asyncio
async def test_ws_multiple_clients_all_receive_broadcast(
    app, client: AsyncClient
) -> None:
    """All connected clients for a gathering receive the same broadcast."""
    token = await _register_and_login(client, "wsok5@test.com")
    gid = await _create_gathering(client, token)

    await client.put(
        f"/api/v1/gatherings/{gid}/budget",
        json={"currency": "EUR", "host_budget_limit": "1000.00"},
        headers={"Authorization": f"Bearer {token}"},
    )

    sync_client = TestClient(app)
    with (
        sync_client.websocket_connect(_ws_url(gid, token)) as ws1,
        sync_client.websocket_connect(_ws_url(gid, token)) as ws2,
    ):
        # Both clients receive the initial state push
        ws1.receive_text()
        ws2.receive_text()

        # One mutation
        await client.post(
            f"/api/v1/gatherings/{gid}/budget/entries",
            json={"description": "Flowers", "amount": "45.00"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Both should receive the broadcast
        d1 = json.loads(ws1.receive_text())
        d2 = json.loads(ws2.receive_text())

        assert d1["total_spent"] == "45.00"
        assert d2["total_spent"] == "45.00"
