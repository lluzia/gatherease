"""Menu and dish service."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.menus.schemas import (
    AddDishRequest,
    DishResponse,
    MenuResponse,
    UpdateDishRequest,
    dish_to_dict,
)
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.dish import Dish
from app.models.gathering import Gathering
from app.models.menu import Menu
from app.models.user import User

logger = structlog.get_logger(__name__)


class MenuService:
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
            raise ForbiddenError("Only the host can manage the menu.")

    async def _get_or_create_menu(self, gathering_id: uuid.UUID) -> Menu:
        """Each gathering has one active menu — create it lazily on first dish."""
        result = await self._db.execute(
            select(Menu).where(Menu.gathering_id == gathering_id)
        )
        menu = result.scalar_one_or_none()
        if menu is None:
            menu = Menu(gathering_id=gathering_id, name="Menu")
            self._db.add(menu)
            await self._db.flush()
            await self._db.refresh(menu)
        return menu

    async def _get_dish_or_404(self, dish_id: uuid.UUID) -> Dish:
        result = await self._db.execute(select(Dish).where(Dish.id == dish_id))
        dish = result.scalar_one_or_none()
        if dish is None:
            raise NotFoundError("Dish not found.")
        return dish

    # ── Menu ─────────────────────────────────────────────────────────────────

    async def get_menu(self, gathering_id: uuid.UUID, user: User) -> MenuResponse:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)

        result = await self._db.execute(
            select(Menu).where(Menu.gathering_id == gathering_id)
        )
        menu = result.scalar_one_or_none()

        if menu is None:
            # No menu yet — return empty
            return MenuResponse(
                id=uuid.uuid4(),
                gathering_id=gathering_id,
                name="Menu",
                dishes=[],
                created_at=gathering.created_at,
                updated_at=gathering.updated_at,
            )

        dishes_result = await self._db.execute(
            select(Dish)
            .where(Dish.menu_id == menu.id)
            .order_by(Dish.sort_order, Dish.created_at)
        )
        dishes = list(dishes_result.scalars().all())

        return MenuResponse(
            id=menu.id,
            gathering_id=gathering_id,
            name=menu.name,
            dishes=[DishResponse(**dish_to_dict(d)) for d in dishes],
            created_at=menu.created_at,
            updated_at=menu.updated_at,
        )

    # ── Dishes ────────────────────────────────────────────────────────────────

    async def add_dish(
        self,
        gathering_id: uuid.UUID,
        payload: AddDishRequest,
        user: User,
    ) -> Dish:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        menu = await self._get_or_create_menu(gathering_id)

        dish = Dish(
            menu_id=menu.id,
            name=payload.name,
            category=payload.category.value,
            assigned_to=payload.assigned_to,
            is_host_prepared=payload.is_host_prepared,
            servings=payload.servings,
            sort_order=payload.sort_order,
        )
        self._db.add(dish)
        await self._db.flush()
        await self._db.refresh(dish)
        logger.info("dish_added", dish_id=str(dish.id), gathering_id=str(gathering_id))
        return dish

    async def update_dish(
        self,
        gathering_id: uuid.UUID,
        dish_id: uuid.UUID,
        payload: UpdateDishRequest,
        user: User,
    ) -> Dish:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        dish = await self._get_dish_or_404(dish_id)

        updates = payload.model_dump(exclude_none=True)
        if "category" in updates:
            updates["category"] = updates["category"].value
        for field, value in updates.items():
            setattr(dish, field, value)

        self._db.add(dish)
        await self._db.flush()
        await self._db.refresh(dish)
        return dish

    async def delete_dish(
        self,
        gathering_id: uuid.UUID,
        dish_id: uuid.UUID,
        user: User,
    ) -> None:
        gathering = await self._get_gathering_or_404(gathering_id)
        self._assert_host(gathering, user)
        dish = await self._get_dish_or_404(dish_id)
        await self._db.delete(dish)
        await self._db.flush()
        logger.info("dish_deleted", dish_id=str(dish_id))
