"""Prep task service."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.prep.schemas import AddPrepTaskRequest, UpdatePrepTaskRequest
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.gathering import Gathering
from app.models.prep_task import PrepTask
from app.models.user import User

logger = structlog.get_logger(__name__)


class PrepService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

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
            raise ForbiddenError("Only the host can manage prep tasks.")

    async def _get_task_or_404(self, task_id: uuid.UUID) -> PrepTask:
        result = await self._db.execute(select(PrepTask).where(PrepTask.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            raise NotFoundError("Prep task not found.")
        return task

    async def list_tasks(self, gathering_id: uuid.UUID, user: User) -> list[PrepTask]:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        result = await self._db.execute(
            select(PrepTask)
            .where(PrepTask.gathering_id == gathering_id)
            .order_by(PrepTask.sort_order, PrepTask.due_at)
        )
        return list(result.scalars().all())

    async def add_task(
        self,
        gathering_id: uuid.UUID,
        payload: AddPrepTaskRequest,
        user: User,
    ) -> PrepTask:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        task = PrepTask(
            gathering_id=gathering_id,
            title=payload.title,
            description=payload.description,
            assigned_to=payload.assigned_to,
            due_at=payload.due_at,
            sort_order=payload.sort_order,
        )
        self._db.add(task)
        await self._db.flush()
        await self._db.refresh(task)
        logger.info("prep_task_added", task_id=str(task.id))
        return task

    async def update_task(
        self,
        gathering_id: uuid.UUID,
        task_id: uuid.UUID,
        payload: UpdatePrepTaskRequest,
        user: User,
    ) -> PrepTask:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        task = await self._get_task_or_404(task_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(task, field, value)
        self._db.add(task)
        await self._db.flush()
        await self._db.refresh(task)
        return task

    async def delete_task(
        self,
        gathering_id: uuid.UUID,
        task_id: uuid.UUID,
        user: User,
    ) -> None:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        task = await self._get_task_or_404(task_id)
        await self._db.delete(task)
        await self._db.flush()
