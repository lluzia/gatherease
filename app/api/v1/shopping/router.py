"""Shopping list router."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.shopping.schemas import (
    AddShoppingItemRequest,
    ShoppingItemResponse,
    ShoppingListResponse,
    UpdateShoppingItemRequest,
    item_to_dict,
)
from app.api.v1.shopping.service import ShoppingService
from app.dependencies import CurrentUser, DbSession

router = APIRouter(tags=["Shopping List"])


def _svc(db: DbSession) -> ShoppingService:
    return ShoppingService(db)


@router.get(
    "/gatherings/{gathering_id}/shopping",
    response_model=ShoppingListResponse,
    summary="Get shopping list",
)
async def get_shopping_list(
    gathering_id: uuid.UUID,
    current_user: CurrentUser,
    service: ShoppingService = Depends(_svc),
) -> ShoppingListResponse:
    return await service.get_list(gathering_id, current_user)


@router.post(
    "/gatherings/{gathering_id}/shopping",
    response_model=ShoppingItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to shopping list",
)
async def add_shopping_item(
    gathering_id: uuid.UUID,
    payload: AddShoppingItemRequest,
    current_user: CurrentUser,
    service: ShoppingService = Depends(_svc),
) -> ShoppingItemResponse:
    item = await service.add_item(gathering_id, payload, current_user)
    return ShoppingItemResponse(**item_to_dict(item))


@router.patch(
    "/gatherings/{gathering_id}/shopping/{item_id}",
    response_model=ShoppingItemResponse,
    summary="Update item (or tick as purchased)",
)
async def update_shopping_item(
    gathering_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: UpdateShoppingItemRequest,
    current_user: CurrentUser,
    service: ShoppingService = Depends(_svc),
) -> ShoppingItemResponse:
    item = await service.update_item(gathering_id, item_id, payload, current_user)
    return ShoppingItemResponse(**item_to_dict(item))


@router.delete(
    "/gatherings/{gathering_id}/shopping/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from shopping list",
)
async def delete_shopping_item(
    gathering_id: uuid.UUID,
    item_id: uuid.UUID,
    current_user: CurrentUser,
    service: ShoppingService = Depends(_svc),
) -> None:
    await service.delete_item(gathering_id, item_id, current_user)
