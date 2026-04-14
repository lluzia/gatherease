"""
Menus router — /api/v1/gatherings/{id}/menu

GET    /gatherings/{id}/menu               get menu with all dishes
POST   /gatherings/{id}/menu/dishes        add a dish
PATCH  /gatherings/{id}/menu/dishes/{did}  update a dish
DELETE /gatherings/{id}/menu/dishes/{did}  delete a dish
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.menus.schemas import (
    AddDishRequest,
    DishResponse,
    MenuResponse,
    UpdateDishRequest,
    dish_to_dict,
)
from app.api.v1.menus.service import MenuService
from app.dependencies import CurrentUser, DbSession

router = APIRouter(tags=["Menus"])


def _svc(db: DbSession) -> MenuService:
    return MenuService(db)


@router.get(
    "/gatherings/{gathering_id}/menu",
    response_model=MenuResponse,
    summary="Get menu with all dishes",
)
async def get_menu(
    gathering_id: uuid.UUID,
    current_user: CurrentUser,
    service: MenuService = Depends(_svc),
) -> MenuResponse:
    return await service.get_menu(gathering_id, current_user)


@router.post(
    "/gatherings/{gathering_id}/menu/dishes",
    response_model=DishResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a dish to the menu",
)
async def add_dish(
    gathering_id: uuid.UUID,
    payload: AddDishRequest,
    current_user: CurrentUser,
    service: MenuService = Depends(_svc),
) -> DishResponse:
    dish = await service.add_dish(gathering_id, payload, current_user)
    return DishResponse(**dish_to_dict(dish))


@router.patch(
    "/gatherings/{gathering_id}/menu/dishes/{dish_id}",
    response_model=DishResponse,
    summary="Update a dish",
)
async def update_dish(
    gathering_id: uuid.UUID,
    dish_id: uuid.UUID,
    payload: UpdateDishRequest,
    current_user: CurrentUser,
    service: MenuService = Depends(_svc),
) -> DishResponse:
    dish = await service.update_dish(gathering_id, dish_id, payload, current_user)
    return DishResponse(**dish_to_dict(dish))


@router.delete(
    "/gatherings/{gathering_id}/menu/dishes/{dish_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a dish",
)
async def delete_dish(
    gathering_id: uuid.UUID,
    dish_id: uuid.UUID,
    current_user: CurrentUser,
    service: MenuService = Depends(_svc),
) -> None:
    await service.delete_dish(gathering_id, dish_id, current_user)
