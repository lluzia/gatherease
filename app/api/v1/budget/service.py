"""Budget service."""

from __future__ import annotations

import uuid
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.budget.schemas import (
    AddEntryRequest,
    BudgetEntryResponse,
    BudgetResponse,
    SetBudgetRequest,
    entry_to_dict,
)
from app.core.exceptions import ForbiddenError, GatheringNotFoundError, NotFoundError
from app.db.enums import BudgetEntryType
from app.models.budget import Budget
from app.models.budget_entry import BudgetEntry
from app.models.gathering import Gathering
from app.models.user import User

logger = structlog.get_logger(__name__)


class BudgetService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _get_gathering_or_404(self, gathering_id: uuid.UUID) -> Gathering:
        result = await self._db.execute(
            select(Gathering).where(Gathering.id == gathering_id)
        )
        gathering = result.scalar_one_or_none()
        if gathering is None:
            raise GatheringNotFoundError()
        return gathering

    def _assert_host(self, gathering: Gathering, user: User) -> None:
        if gathering.host_id != user.id:
            raise ForbiddenError("Only the host can manage the budget.")

    async def _get_or_create_budget(self, gathering_id: uuid.UUID) -> Budget:
        result = await self._db.execute(
            select(Budget).where(Budget.gathering_id == gathering_id)
        )
        budget = result.scalar_one_or_none()
        if budget is None:
            budget = Budget(gathering_id=gathering_id)
            self._db.add(budget)
            await self._db.flush()
            await self._db.refresh(budget)
        return budget

    async def _build_response(self, budget: Budget) -> BudgetResponse:
        entries_result = await self._db.execute(
            select(BudgetEntry)
            .where(BudgetEntry.budget_id == budget.id)
            .order_by(BudgetEntry.created_at.desc())
        )
        entries = list(entries_result.scalars().all())

        host_total = sum(
            Decimal(str(e.amount))
            for e in entries
            if (e.entry_type.value if hasattr(e.entry_type, "value") else e.entry_type)
            == BudgetEntryType.HOST.value
        )
        participant_total = sum(
            Decimal(str(e.amount))
            for e in entries
            if (e.entry_type.value if hasattr(e.entry_type, "value") else e.entry_type)
            == BudgetEntryType.PARTICIPANT.value
        )
        total = host_total + participant_total

        host_remaining = None
        if budget.host_budget_limit is not None:
            host_remaining = Decimal(str(budget.host_budget_limit)) - host_total

        return BudgetResponse(
            id=budget.id,
            gathering_id=budget.gathering_id,
            currency=budget.currency,
            host_budget_limit=budget.host_budget_limit,
            participant_target=budget.participant_target,
            host_total_spent=host_total,
            participant_total_spent=participant_total,
            total_spent=total,
            host_remaining=host_remaining,
            version=budget.version,
            entries=[BudgetEntryResponse(**entry_to_dict(e)) for e in entries],
        )

    async def get_budget(self, gathering_id: uuid.UUID, user: User) -> BudgetResponse:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        budget = await self._get_or_create_budget(gathering_id)
        return await self._build_response(budget)

    async def set_budget(
        self,
        gathering_id: uuid.UUID,
        payload: SetBudgetRequest,
        user: User,
    ) -> BudgetResponse:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        budget = await self._get_or_create_budget(gathering_id)

        budget.currency = payload.currency
        budget.host_budget_limit = payload.host_budget_limit
        budget.participant_target = payload.participant_target
        budget.version += 1

        self._db.add(budget)
        await self._db.flush()
        await self._db.refresh(budget)
        logger.info("budget_set", gathering_id=str(gathering_id))
        return await self._build_response(budget)

    async def add_entry(
        self,
        gathering_id: uuid.UUID,
        payload: AddEntryRequest,
        user: User,
    ) -> BudgetResponse:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        budget = await self._get_or_create_budget(gathering_id)

        entry = BudgetEntry(
            budget_id=budget.id,
            entry_type=BudgetEntryType.HOST.value,
            description=payload.description,
            amount=payload.amount,
            paid_by=payload.paid_by,
            notes=payload.notes,
        )
        self._db.add(entry)
        budget.version += 1
        self._db.add(budget)
        await self._db.flush()
        logger.info(
            "budget_entry_added",
            entry_id=str(entry.id),
            amount=str(payload.amount),
        )
        return await self._build_response(budget)

    async def delete_entry(
        self,
        gathering_id: uuid.UUID,
        entry_id: uuid.UUID,
        user: User,
    ) -> BudgetResponse:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        budget = await self._get_or_create_budget(gathering_id)

        result = await self._db.execute(
            select(BudgetEntry).where(
                BudgetEntry.id == entry_id,
                BudgetEntry.budget_id == budget.id,
            )
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise NotFoundError("Budget entry not found.")

        await self._db.delete(entry)
        budget.version += 1
        self._db.add(budget)
        await self._db.flush()
        return await self._build_response(budget)
