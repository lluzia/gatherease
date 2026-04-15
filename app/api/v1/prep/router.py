"""Prep tasks router — /api/v1/gatherings/{id}/prep"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.prep.schemas import (
    AddPrepTaskRequest,
    PrepTaskListResponse,
    PrepTaskResponse,
    UpdatePrepTaskRequest,
    task_to_dict,
)
from app.api.v1.prep.service import PrepService
from app.dependencies import CurrentUser, DbSession

router = APIRouter(tags=["Prep Tasks"])


def _svc(db: DbSession) -> PrepService:
    return PrepService(db)


@router.get(
    "/gatherings/{gathering_id}/prep",
    response_model=PrepTaskListResponse,
    summary="Get prep task list",
)
async def list_prep_tasks(
    gathering_id: uuid.UUID,
    current_user: CurrentUser,
    service: PrepService = Depends(_svc),
) -> PrepTaskListResponse:
    tasks = await service.list_tasks(gathering_id, current_user)
    task_dicts = [task_to_dict(t) for t in tasks]
    completed = sum(1 for t in task_dicts if t["is_completed"])
    return PrepTaskListResponse(
        tasks=[PrepTaskResponse(**t) for t in task_dicts],
        total=len(tasks),
        completed=completed,
        remaining=len(tasks) - completed,
    )


@router.post(
    "/gatherings/{gathering_id}/prep",
    response_model=PrepTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a prep task",
)
async def add_prep_task(
    gathering_id: uuid.UUID,
    payload: AddPrepTaskRequest,
    current_user: CurrentUser,
    service: PrepService = Depends(_svc),
) -> PrepTaskResponse:
    task = await service.add_task(gathering_id, payload, current_user)
    return PrepTaskResponse(**task_to_dict(task))


@router.patch(
    "/gatherings/{gathering_id}/prep/{task_id}",
    response_model=PrepTaskResponse,
    summary="Update a prep task",
)
async def update_prep_task(
    gathering_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: UpdatePrepTaskRequest,
    current_user: CurrentUser,
    service: PrepService = Depends(_svc),
) -> PrepTaskResponse:
    task = await service.update_task(gathering_id, task_id, payload, current_user)
    return PrepTaskResponse(**task_to_dict(task))


@router.delete(
    "/gatherings/{gathering_id}/prep/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a prep task",
)
async def delete_prep_task(
    gathering_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: CurrentUser,
    service: PrepService = Depends(_svc),
) -> None:
    await service.delete_task(gathering_id, task_id, current_user)
