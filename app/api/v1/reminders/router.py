"""
Reminders router — /api/v1/gatherings/{id}/reminders

GET    /gatherings/{id}/reminders               list all reminders
POST   /gatherings/{id}/reminders               create a reminder
PATCH  /gatherings/{id}/reminders/{rid}         update a reminder
DELETE /gatherings/{id}/reminders/{rid}         delete a reminder
POST   /gatherings/{id}/reminders/{rid}/send    manually dispatch now
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.reminders.schemas import (
    CreateReminderRequest,
    ReminderListResponse,
    ReminderResponse,
    UpdateReminderRequest,
    reminder_to_dict,
)
from app.api.v1.reminders.service import ReminderService
from app.dependencies import CurrentUser, DbSession

router = APIRouter(tags=["Reminders"])


def _svc(db: DbSession) -> ReminderService:
    return ReminderService(db)


@router.get(
    "/gatherings/{gathering_id}/reminders",
    response_model=ReminderListResponse,
    summary="List reminders for a gathering",
)
async def list_reminders(
    gathering_id: uuid.UUID,
    current_user: CurrentUser,
    service: ReminderService = Depends(_svc),
) -> ReminderListResponse:
    reminders = await service.list_reminders(gathering_id, current_user)
    dicts = [reminder_to_dict(r) for r in reminders]
    sent = sum(1 for d in dicts if d["is_sent"])
    return ReminderListResponse(
        reminders=[ReminderResponse(**d) for d in dicts],
        total=len(dicts),
        pending=len(dicts) - sent,
        sent=sent,
    )


@router.post(
    "/gatherings/{gathering_id}/reminders",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a reminder",
)
async def create_reminder(
    gathering_id: uuid.UUID,
    payload: CreateReminderRequest,
    current_user: CurrentUser,
    service: ReminderService = Depends(_svc),
) -> ReminderResponse:
    reminder = await service.create_reminder(gathering_id, payload, current_user)
    return ReminderResponse(**reminder_to_dict(reminder))


@router.patch(
    "/gatherings/{gathering_id}/reminders/{reminder_id}",
    response_model=ReminderResponse,
    summary="Update a reminder",
)
async def update_reminder(
    gathering_id: uuid.UUID,
    reminder_id: uuid.UUID,
    payload: UpdateReminderRequest,
    current_user: CurrentUser,
    service: ReminderService = Depends(_svc),
) -> ReminderResponse:
    reminder = await service.update_reminder(
        gathering_id, reminder_id, payload, current_user
    )
    return ReminderResponse(**reminder_to_dict(reminder))


@router.delete(
    "/gatherings/{gathering_id}/reminders/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a reminder",
)
async def delete_reminder(
    gathering_id: uuid.UUID,
    reminder_id: uuid.UUID,
    current_user: CurrentUser,
    service: ReminderService = Depends(_svc),
) -> None:
    await service.delete_reminder(gathering_id, reminder_id, current_user)


@router.post(
    "/gatherings/{gathering_id}/reminders/{reminder_id}/send",
    response_model=ReminderResponse,
    summary="Manually dispatch a reminder now",
    description=(
        "Marks the reminder as sent and publishes a `reminder.fire` event to SNS. "
        "Useful for testing and for ops to manually trigger overdue reminders. "
        "Returns 400 if the reminder is already sent."
    ),
)
async def send_reminder(
    gathering_id: uuid.UUID,
    reminder_id: uuid.UUID,
    current_user: CurrentUser,
    service: ReminderService = Depends(_svc),
) -> ReminderResponse:
    reminder = await service.dispatch_reminder(
        gathering_id, reminder_id, current_user
    )
    return ReminderResponse(**reminder_to_dict(reminder))
