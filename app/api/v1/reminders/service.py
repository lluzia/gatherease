"""Reminders service — CRUD + dispatch logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.reminders.schemas import CreateReminderRequest, UpdateReminderRequest
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.gathering import Gathering
from app.models.reminder import Reminder
from app.models.user import User

logger = structlog.get_logger(__name__)


class ReminderService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
            raise ForbiddenError("Only the host can manage reminders.")

    async def _get_reminder_or_404(self, reminder_id: uuid.UUID) -> Reminder:
        result = await self._db.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        if reminder is None:
            raise NotFoundError("Reminder not found.")
        return reminder

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def list_reminders(
        self, gathering_id: uuid.UUID, user: User
    ) -> list[Reminder]:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        result = await self._db.execute(
            select(Reminder)
            .where(Reminder.gathering_id == gathering_id)
            .order_by(Reminder.scheduled_at)
        )
        return list(result.scalars().all())

    async def create_reminder(
        self,
        gathering_id: uuid.UUID,
        payload: CreateReminderRequest,
        user: User,
    ) -> Reminder:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)

        reminder = Reminder(
            gathering_id=gathering_id,
            title=payload.title,
            body=payload.body,
            reminder_type=payload.reminder_type,
            scheduled_at=payload.scheduled_at,
        )
        self._db.add(reminder)
        await self._db.flush()
        await self._db.refresh(reminder)
        logger.info(
            "reminder_created",
            reminder_id=str(reminder.id),
            scheduled_at=str(reminder.scheduled_at),
        )
        return reminder

    async def update_reminder(
        self,
        gathering_id: uuid.UUID,
        reminder_id: uuid.UUID,
        payload: UpdateReminderRequest,
        user: User,
    ) -> Reminder:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        reminder = await self._get_reminder_or_404(reminder_id)

        if reminder.is_sent:
            raise BadRequestError("Cannot modify a reminder that has already been sent.")

        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(reminder, field, value)

        self._db.add(reminder)
        await self._db.flush()
        await self._db.refresh(reminder)
        return reminder

    async def delete_reminder(
        self,
        gathering_id: uuid.UUID,
        reminder_id: uuid.UUID,
        user: User,
    ) -> None:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        reminder = await self._get_reminder_or_404(reminder_id)
        await self._db.delete(reminder)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Dispatch (manual trigger or called by scheduler)
    # ------------------------------------------------------------------

    async def dispatch_reminder(
        self,
        gathering_id: uuid.UUID,
        reminder_id: uuid.UUID,
        user: User,
    ) -> Reminder:
        """Mark the reminder as sent and publish to SNS.

        This is the manual trigger endpoint used in tests and by ops.
        The scheduled background dispatcher (APScheduler / EventBridge)
        calls the same core logic via `dispatch_reminder_by_id()`.
        """
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        reminder = await self._get_reminder_or_404(reminder_id)

        if reminder.is_sent:
            raise BadRequestError("Reminder has already been sent.")

        await self._do_dispatch(reminder, gathering_name=gathering.name, host=user)
        return reminder

    async def dispatch_reminder_by_id(self, reminder_id: uuid.UUID) -> None:
        """Internal entry point for the background scheduler.

        Looks up the reminder and its gathering host, then dispatches.
        Silently skips already-sent reminders (idempotent).
        """
        reminder = await self._get_reminder_or_404(reminder_id)
        if reminder.is_sent:
            logger.info("reminder_already_sent_skip", reminder_id=str(reminder_id))
            return

        # Load gathering for name + host FCM token
        result = await self._db.execute(
            select(Gathering).where(Gathering.id == reminder.gathering_id)
        )
        gathering = result.scalar_one_or_none()
        if gathering is None:
            logger.error("reminder_orphan_no_gathering", reminder_id=str(reminder_id))
            return

        result = await self._db.execute(
            select(User).where(User.id == gathering.host_id)
        )
        host = result.scalar_one_or_none()
        if host is None:
            logger.error("reminder_orphan_no_host", reminder_id=str(reminder_id))
            return

        await self._do_dispatch(reminder, gathering_name=gathering.name, host=host)

    async def _do_dispatch(
        self,
        reminder: Reminder,
        *,
        gathering_name: str,
        host: User,
    ) -> None:
        """Core dispatch: mark sent + publish SNS event. Non-blocking on SNS failure."""
        from app.services.sns import publish_reminder_fire

        # Mark sent before publishing — if SNS fails we still record the attempt
        reminder.is_sent = True
        reminder.sent_at = datetime.now(UTC)
        self._db.add(reminder)
        await self._db.flush()
        await self._db.refresh(reminder)

        # Fire-and-forget SNS publish (errors are logged, not raised)
        await publish_reminder_fire(
            reminder_id=str(reminder.id),
            gathering_id=str(reminder.gathering_id),
            gathering_name=gathering_name,
            title=reminder.title,
            body=reminder.body,
            reminder_type=str(reminder.reminder_type.value)
            if hasattr(reminder.reminder_type, "value")
            else str(reminder.reminder_type),
            fcm_token=host.fcm_token,
        )

        logger.info(
            "reminder_dispatched",
            reminder_id=str(reminder.id),
            has_fcm=bool(host.fcm_token),
        )
