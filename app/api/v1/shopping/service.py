"""Shopping list service."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.shopping.schemas import (
    AddShoppingItemRequest,
    ShoppingItemResponse,
    ShoppingListResponse,
    UpdateShoppingItemRequest,
    item_to_dict,
)
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.gathering import Gathering
from app.models.shopping_item import ShoppingItem
from app.models.user import User

logger = structlog.get_logger(__name__)


class ShoppingService:
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
            raise ForbiddenError("Only the host can manage the shopping list.")

    async def _get_item_or_404(self, item_id: uuid.UUID) -> ShoppingItem:
        result = await self._db.execute(
            select(ShoppingItem).where(ShoppingItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundError("Shopping item not found.")
        return item

    async def get_list(
        self, gathering_id: uuid.UUID, user: User
    ) -> ShoppingListResponse:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)

        result = await self._db.execute(
            select(ShoppingItem)
            .where(ShoppingItem.gathering_id == gathering_id)
            .order_by(ShoppingItem.is_purchased, ShoppingItem.created_at)
        )
        items = list(result.scalars().all())
        purchased = sum(1 for i in items if i.is_purchased)

        return ShoppingListResponse(
            items=[ShoppingItemResponse(**item_to_dict(i)) for i in items],
            total=len(items),
            purchased=purchased,
            remaining=len(items) - purchased,
        )

    async def add_item(
        self,
        gathering_id: uuid.UUID,
        payload: AddShoppingItemRequest,
        user: User,
    ) -> ShoppingItem:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)

        item = ShoppingItem(
            gathering_id=gathering_id,
            name=payload.name,
            quantity=payload.quantity,
            unit=payload.unit,
            assigned_to=payload.assigned_to,
            is_auto_generated=False,
        )
        self._db.add(item)
        await self._db.flush()
        await self._db.refresh(item)
        logger.info("shopping_item_added", item_id=str(item.id))
        return item

    async def update_item(
        self,
        gathering_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: UpdateShoppingItemRequest,
        user: User,
    ) -> ShoppingItem:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        item = await self._get_item_or_404(item_id)

        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(item, field, value)

        self._db.add(item)
        await self._db.flush()
        await self._db.refresh(item)
        return item

    async def delete_item(
        self,
        gathering_id: uuid.UUID,
        item_id: uuid.UUID,
        user: User,
    ) -> None:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        item = await self._get_item_or_404(item_id)
        await self._db.delete(item)
        await self._db.flush()
