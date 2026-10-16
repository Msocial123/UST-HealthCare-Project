import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    AccessToken,
    CurrentClock,
    CurrentSettings,
    DbSession,
    FacilityClientDep,
    require_permission,
)
from app.domain.roles import Permission
from app.domain.scheduling import MAX_SLOT_RANGE_DAYS
from app.schemas.common import ErrorResponse
from app.schemas.slot import SlotRead, SlotsResponse
from app.services.slot_service import SlotService

router = APIRouter(
    tags=["slots"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)


@router.get(
    "/providers/{provider_id}/slots",
    response_model=SlotsResponse,
    dependencies=[Depends(require_permission(Permission.SLOTS_READ))],
    summary=f"Advisory free slots, max {MAX_SLOT_RANGE_DAYS}-day range (RECEPTIONIST, DOCTOR, ADMIN)",
    description=(
        "Slots are computed from working hours (facility-local time) plus EXTRA_HOURS, minus LEAVE, "
        "HOLIDAY and BLOCKED exceptions, and returned in UTC with the facility timezone. They are "
        "advisory only: nothing is reserved, and the Appointment service owns booking correctness."
    ),
)
def get_slots(
    provider_id: uuid.UUID,
    db: DbSession,
    clock: CurrentClock,
    settings: CurrentSettings,
    facilities: FacilityClientDep,
    token: AccessToken,
    facility_id: Annotated[uuid.UUID, Query()],
    date_from: Annotated[date, Query(description="Facility-local date (inclusive)")],
    date_to: Annotated[date, Query(description="Facility-local date (inclusive)")],
) -> SlotsResponse:
    service = SlotService(db, clock, facilities, extra_slot_minutes=settings.extra_hours_slot_minutes)
    result = service.query(provider_id, facility_id, date_from, date_to, token)
    zone = result.facility.zone
    return SlotsResponse(
        provider_id=provider_id,
        facility_id=facility_id,
        timezone=result.facility.timezone,
        date_from=date_from,
        date_to=date_to,
        slots=[
            SlotRead(
                start_utc=slot.start_utc,
                end_utc=slot.end_utc,
                start_local=slot.start_utc.astimezone(zone),
                end_local=slot.end_utc.astimezone(zone),
                source=slot.source,
            )
            for slot in result.slots
        ],
    )
