"""
Budget router — /api/v1/gatherings/{id}/budget

GET    /gatherings/{id}/budget              get budget + entries
PUT    /gatherings/{id}/budget              set budget limits
POST   /gatherings/{id}/budget/entries      add an expense entry
DELETE /gatherings/{id}/budget/entries/{eid} delete an entry

WebSocket:
WS     /ws/gatherings/{id}/budget           real-time spend sync
"""

from __future__ import annotations

import json
import uuid

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status

from app.api.v1.budget.schemas import (
    AddEntryRequest,
    BudgetResponse,
    SetBudgetRequest,
)
from app.api.v1.budget.service import BudgetService
from app.dependencies import CurrentUser, DbSession

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Budget"])
ws_router = APIRouter(tags=["Budget WebSocket"])


def _svc(db: DbSession) -> BudgetService:
    return BudgetService(db)


# ---------------------------------------------------------------------------
# Connection manager — tracks active WebSocket connections per gathering
# ---------------------------------------------------------------------------


class ConnectionManager:
    def __init__(self) -> None:
        # gathering_id → set of WebSocket connections
        self._rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, gathering_id: str, ws: WebSocket) -> None:
        # accept() is called by the route handler before auth, so we
        # only register the connection here without calling accept() again.
        if gathering_id not in self._rooms:
            self._rooms[gathering_id] = set()
        self._rooms[gathering_id].add(ws)
        logger.info("ws_connected", gathering_id=gathering_id)

    def disconnect(self, gathering_id: str, ws: WebSocket) -> None:
        if gathering_id in self._rooms:
            self._rooms[gathering_id].discard(ws)
            if not self._rooms[gathering_id]:
                del self._rooms[gathering_id]
        logger.info("ws_disconnected", gathering_id=gathering_id)

    async def broadcast(self, gathering_id: str, data: dict) -> None:
        """Send budget update to all connected clients for this gathering."""
        room = self._rooms.get(gathering_id, set())
        dead: set[WebSocket] = set()
        for ws in room:
            try:
                await ws.send_text(json.dumps(data, default=str))
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(gathering_id, ws)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/gatherings/{gathering_id}/budget",
    response_model=BudgetResponse,
    summary="Get budget with all entries",
)
async def get_budget(
    gathering_id: uuid.UUID,
    current_user: CurrentUser,
    service: BudgetService = Depends(_svc),
) -> BudgetResponse:
    return await service.get_budget(gathering_id, current_user)


@router.put(
    "/gatherings/{gathering_id}/budget",
    response_model=BudgetResponse,
    summary="Set budget limits",
)
async def set_budget(
    gathering_id: uuid.UUID,
    payload: SetBudgetRequest,
    current_user: CurrentUser,
    service: BudgetService = Depends(_svc),
) -> BudgetResponse:
    result = await service.set_budget(gathering_id, payload, current_user)
    await manager.broadcast(str(gathering_id), result.model_dump())
    return result


@router.post(
    "/gatherings/{gathering_id}/budget/entries",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an expense entry",
)
async def add_budget_entry(
    gathering_id: uuid.UUID,
    payload: AddEntryRequest,
    current_user: CurrentUser,
    service: BudgetService = Depends(_svc),
) -> BudgetResponse:
    result = await service.add_entry(gathering_id, payload, current_user)
    await manager.broadcast(str(gathering_id), result.model_dump())
    return result


@router.delete(
    "/gatherings/{gathering_id}/budget/entries/{entry_id}",
    response_model=BudgetResponse,
    summary="Delete an expense entry",
)
async def delete_budget_entry(
    gathering_id: uuid.UUID,
    entry_id: uuid.UUID,
    current_user: CurrentUser,
    service: BudgetService = Depends(_svc),
) -> BudgetResponse:
    result = await service.delete_entry(gathering_id, entry_id, current_user)
    await manager.broadcast(str(gathering_id), result.model_dump())
    return result


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@ws_router.websocket("/ws/gatherings/{gathering_id}/budget")
async def budget_websocket(
    gathering_id: str,
    websocket: WebSocket,
    db: DbSession,
    token: str | None = None,  # passed as ?token=<jwt> query param
) -> None:
    """
    Connect to receive real-time budget updates for a gathering.

    Auth: pass your JWT as a query parameter:
      ws://localhost:8000/ws/gatherings/{id}/budget?token=<access_token>

    On connect: sends the current budget state immediately.
    On any REST update: broadcasts the new budget to all connected clients.
    On reconnect: client should call GET /budget to resync if WS was closed.

    Close codes:
      4001 — missing or invalid token
      4002 — token expired
    """
    from app.core.exceptions import ExpiredTokenError, InvalidTokenError
    from app.core.security import decode_token

    # Accept the handshake unconditionally first — Starlette requires
    # accept() before close() can send a proper close frame with a code.
    # Closing before accept() raises WebSocketDisconnect in the test client
    # and sends no frame at all in production.
    await websocket.accept()

    # Token is always required — browsers can't send Authorization headers
    # over WebSocket, so clients pass the JWT as ?token=<access_token>.
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        await decode_token(token)
    except ExpiredTokenError as e:
        await websocket.close(code=4002, reason=str(e))
        return
    except InvalidTokenError as e:
        await websocket.close(code=4001, reason=str(e))
        return

    # Auth passed — register in the room (accept already called above)
    await manager.connect(gathering_id, websocket)
    try:
        # Send current state immediately on connect
        from sqlalchemy import select

        from app.models.budget import Budget

        result = await db.execute(
            select(Budget).where(Budget.gathering_id == uuid.UUID(gathering_id))
        )
        budget = result.scalar_one_or_none()
        if budget:
            svc = BudgetService(db)
            response = await svc._build_response(budget)
            await websocket.send_text(json.dumps(response.model_dump(), default=str))

        # Keep connection alive — client sends "ping", we echo "pong"
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        manager.disconnect(gathering_id, websocket)
    except Exception as e:
        logger.error("ws_error", error=str(e), gathering_id=gathering_id)
        manager.disconnect(gathering_id, websocket)
