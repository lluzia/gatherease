"""Gathering service — all business logic for gatherings, invites and RSVPs."""

from __future__ import annotations

import secrets
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.gatherings.schemas import (
    CreateGatheringRequest,
    GuestListResponse,
    GuestPageResponse,
    RSVPRequest,
    RSVPResponse,
    UpdateGatheringRequest,
)
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.enums import RSVPStatus
from app.models.gathering import Gathering
from app.models.guest_rsvp import GuestRSVP
from app.models.user import User

logger = structlog.get_logger(__name__)


class GatheringService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _get_gathering_or_404(self, gathering_id: uuid.UUID) -> Gathering:
        result = await self._db.execute(
            select(Gathering).where(Gathering.id == gathering_id)
        )
        gathering = result.scalar_one_or_none()
        if gathering is None:
            raise NotFoundError("Gathering not found.")
        return gathering

    def _assert_host(self, gathering: Gathering, user: User) -> None:
        if gathering.host_id != user.id:
            raise ForbiddenError("Only the host can perform this action.")

    # ── CRUD ─────────────────────────────────────────────────────────────────

    async def create(self, payload: CreateGatheringRequest, host: User) -> Gathering:
        gathering = Gathering(
            host_id=host.id,
            name=payload.name,
            description=payload.description,
            location=payload.location,
            event_date=payload.event_date,
            guest_count_estimate=payload.guest_count_estimate,
        )
        self._db.add(gathering)
        await self._db.flush()
        await self._db.refresh(gathering)
        logger.info(
            "gathering_created",
            gathering_id=str(gathering.id),
            host_id=str(host.id),
        )
        return gathering

    async def list_for_host(self, host: User) -> list[Gathering]:
        result = await self._db.execute(
            select(Gathering)
            .where(Gathering.host_id == host.id)
            .where(Gathering.is_archived != True)  # noqa: E712 — works on SQLite and PG
            .order_by(Gathering.event_date.asc())
        )
        return list(result.scalars().all())

    async def get(self, gathering_id: uuid.UUID, user: User) -> Gathering:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        return gathering

    async def update(
        self,
        gathering_id: uuid.UUID,
        payload: UpdateGatheringRequest,
        user: User,
    ) -> Gathering:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)

        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(gathering, field, value)

        self._db.add(gathering)
        await self._db.flush()
        await self._db.refresh(gathering)
        return gathering

    async def delete(self, gathering_id: uuid.UUID, user: User) -> None:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        await self._db.delete(gathering)
        await self._db.flush()
        logger.info("gathering_deleted", gathering_id=str(gathering_id))

    # ── Invite ────────────────────────────────────────────────────────────────

    async def generate_invite(self, gathering_id: uuid.UUID, user: User) -> Gathering:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)

        if not gathering.invite_token:
            gathering.invite_token = secrets.token_urlsafe(24)
            self._db.add(gathering)
            await self._db.flush()
            await self._db.refresh(gathering)

        return gathering

    async def get_guest_page(self, invite_token: str) -> GuestPageResponse:
        """Public endpoint — no auth. Returns what the host chose to show."""
        result = await self._db.execute(
            select(Gathering).where(Gathering.invite_token == invite_token)
        )
        gathering = result.scalar_one_or_none()
        if gathering is None:
            raise NotFoundError("Invite link not found.")

        # Get host name
        host_result = await self._db.execute(
            select(User).where(User.id == gathering.host_id)
        )
        host = host_result.scalar_one_or_none()

        # Get dish names if host made menu visible
        menu_dishes: list[str] | None = None
        if gathering.show_menu:
            from app.models.dish import Dish
            from app.models.menu import Menu

            dishes_result = await self._db.execute(
                select(Dish.name)
                .join(Menu, Dish.menu_id == Menu.id)
                .where(Menu.gathering_id == gathering.id)
                .order_by(Dish.sort_order)
            )
            menu_dishes = list(dishes_result.scalars().all())

        return GuestPageResponse(
            gathering_name=gathering.name,
            event_date=gathering.event_date,
            host_name=host.full_name if host else None,
            location=gathering.location if gathering.show_location else None,
            menu_dishes=menu_dishes,
        )

    # ── RSVP ─────────────────────────────────────────────────────────────────

    async def submit_rsvp(self, invite_token: str, payload: RSVPRequest) -> GuestRSVP:
        """Public endpoint — no auth required."""
        result = await self._db.execute(
            select(Gathering).where(Gathering.invite_token == invite_token)
        )
        gathering = result.scalar_one_or_none()
        if gathering is None:
            raise NotFoundError("Invite link not found.")

        rsvp = GuestRSVP(
            gathering_id=gathering.id,
            guest_name=payload.guest_name,
            guest_email=payload.guest_email,
            status=RSVPStatus(payload.status).value,
            message=payload.message,
        )
        self._db.add(rsvp)
        await self._db.flush()
        logger.info(
            "rsvp_submitted",
            gathering_id=str(gathering.id),
            status=payload.status,
        )
        return rsvp

    async def get_guest_list(
        self, gathering_id: uuid.UUID, user: User
    ) -> GuestListResponse:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)

        result = await self._db.execute(
            select(GuestRSVP)
            .where(GuestRSVP.gathering_id == gathering_id)
            .order_by(GuestRSVP.created_at.asc())
        )
        guests = list(result.scalars().all())

        def count_status(s: RSVPStatus) -> int:
            return sum(1 for g in guests if g.status == s)

        return GuestListResponse(
            guests=[RSVPResponse.model_validate(g) for g in guests],
            total=len(guests),
            accepted=count_status(RSVPStatus.ACCEPTED),
            declined=count_status(RSVPStatus.DECLINED),
            maybe=count_status(RSVPStatus.MAYBE),
            pending=count_status(RSVPStatus.PENDING),
        )
