"""
Gatherings router — /api/v1/gatherings

POST   /gatherings                        create a gathering
GET    /gatherings                        list host's gatherings
GET    /gatherings/{id}                   get one gathering
PATCH  /gatherings/{id}                   update a gathering
DELETE /gatherings/{id}                   delete a gathering
POST   /gatherings/{id}/invite            generate invite link
GET    /gatherings/{id}/guests            host sees guest list

Public (no auth):
GET    /invite/{token}                    guest public page
POST   /invite/{token}/rsvp              submit RSVP
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.gatherings.schemas import (
    CreateGatheringRequest,
    GatheringListResponse,
    GatheringResponse,
    GuestListResponse,
    GuestPageResponse,
    InviteLinkResponse,
    RSVPRequest,
    RSVPResponse,
    UpdateGatheringRequest,
    gathering_to_dict,
)
from app.api.v1.gatherings.service import GatheringService
from app.dependencies import CurrentUser, DbSession

router = APIRouter(tags=["Gatherings"])
public_router = APIRouter(tags=["Invite"])


def _svc(db: DbSession) -> GatheringService:
    return GatheringService(db)


# ---------------------------------------------------------------------------
# Gathering CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/gatherings",
    response_model=GatheringResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a gathering",
)
async def create_gathering(
    payload: CreateGatheringRequest,
    current_user: CurrentUser,
    service: GatheringService = Depends(_svc),
) -> GatheringResponse:
    gathering = await service.create(payload, current_user)
    return GatheringResponse(**gathering_to_dict(gathering))


@router.get(
    "/gatherings",
    response_model=GatheringListResponse,
    summary="List my gatherings",
)
async def list_gatherings(
    current_user: CurrentUser,
    service: GatheringService = Depends(_svc),
) -> GatheringListResponse:
    gatherings = await service.list_for_host(current_user)
    return GatheringListResponse(
        gatherings=[GatheringResponse(**gathering_to_dict(g)) for g in gatherings],
        total=len(gatherings),
    )


@router.get(
    "/gatherings/{gathering_id}",
    response_model=GatheringResponse,
    summary="Get a gathering",
)
async def get_gathering(
    gathering_id: uuid.UUID,
    current_user: CurrentUser,
    service: GatheringService = Depends(_svc),
) -> GatheringResponse:
    gathering = await service.get(gathering_id, current_user)
    return GatheringResponse(**gathering_to_dict(gathering))


@router.patch(
    "/gatherings/{gathering_id}",
    response_model=GatheringResponse,
    summary="Update a gathering",
)
async def update_gathering(
    gathering_id: uuid.UUID,
    payload: UpdateGatheringRequest,
    current_user: CurrentUser,
    service: GatheringService = Depends(_svc),
) -> GatheringResponse:
    gathering = await service.update(gathering_id, payload, current_user)
    return GatheringResponse(**gathering_to_dict(gathering))


@router.delete(
    "/gatherings/{gathering_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a gathering",
)
async def delete_gathering(
    gathering_id: uuid.UUID,
    current_user: CurrentUser,
    service: GatheringService = Depends(_svc),
) -> None:
    await service.delete(gathering_id, current_user)


# ---------------------------------------------------------------------------
# Invite & Guest list
# ---------------------------------------------------------------------------


@router.post(
    "/gatherings/{gathering_id}/invite",
    response_model=InviteLinkResponse,
    summary="Generate or retrieve invite link",
)
async def generate_invite(
    gathering_id: uuid.UUID,
    current_user: CurrentUser,
    service: GatheringService = Depends(_svc),
) -> InviteLinkResponse:
    gathering = await service.generate_invite(gathering_id, current_user)
    return InviteLinkResponse(
        invite_token=gathering.invite_token,
        invite_url=f"http://localhost:8000/api/v1/i/{gathering.invite_token}",
    )


@router.get(
    "/gatherings/{gathering_id}/guests",
    response_model=GuestListResponse,
    summary="Get guest list with RSVP status",
)
async def get_guest_list(
    gathering_id: uuid.UUID,
    current_user: CurrentUser,
    service: GatheringService = Depends(_svc),
) -> GuestListResponse:
    return await service.get_guest_list(gathering_id, current_user)


# ---------------------------------------------------------------------------
# Public routes (no auth)
# ---------------------------------------------------------------------------


@public_router.get(
    "/i/{invite_token}",
    response_model=GuestPageResponse,
    summary="Guest public page (no login required)",
)
async def guest_page(
    invite_token: str,
    service: GatheringService = Depends(_svc),
) -> GuestPageResponse:
    return await service.get_guest_page(invite_token)


@public_router.post(
    "/i/{invite_token}/rsvp",
    response_model=RSVPResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit RSVP (no login required)",
)
async def submit_rsvp(
    invite_token: str,
    payload: RSVPRequest,
    service: GatheringService = Depends(_svc),
) -> RSVPResponse:
    rsvp = await service.submit_rsvp(invite_token, payload)
    return RSVPResponse.model_validate(rsvp)
