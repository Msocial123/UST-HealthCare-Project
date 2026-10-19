import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status
from pydantic import AwareDatetime

from app.api.deps import (
    AccessToken,
    CurrentClock,
    CurrentPrincipal,
    DbSession,
    SchedulingClientDep,
    require_appointments_enabled,
    require_permission,
)
from app.domain.appointments import AppointmentStatus
from app.domain.roles import Permission
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentRead,
    AppointmentReschedule,
    StatusTransition,
)
from app.schemas.common import ErrorResponse, Page
from app.services.appointment_service import AppointmentService

router = APIRouter(
    prefix="/appointments",
    tags=["appointments"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)

CanRead = Depends(require_permission(Permission.APPOINTMENTS_READ))
CanBook = Depends(require_permission(Permission.APPOINTMENTS_BOOK))
CanTransition = Depends(require_permission(Permission.APPOINTMENTS_TRANSITION))
# Order matters: authorization (401/403) is checked before the feature flag (503).
BookingEnabled = Depends(require_appointments_enabled)
_NOT_FOUND = {404: {"model": ErrorResponse}}
_CONFLICT = {409: {"model": ErrorResponse}}
_DISABLED = {
    503: {
        "model": ErrorResponse,
        "description": "`feature_disabled` when APPOINTMENTS_ENABLED=false; `service_unavailable` when "
        "the optional Scheduling advice check cannot reach the Scheduling service",
    }
}


@router.post(
    "",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CanBook, BookingEnabled],
    responses={**_NOT_FOUND, **_CONFLICT, **_DISABLED},
    summary="Book an appointment (RECEPTIONIST, ADMIN); 409 if the provider is already booked",
)
def book_appointment(
    payload: AppointmentCreate,
    db: DbSession,
    clock: CurrentClock,
    principal: CurrentPrincipal,
    token: AccessToken,
    scheduling: SchedulingClientDep,
) -> AppointmentRead:
    appointment = AppointmentService(db, clock, scheduling=scheduling).book(payload, principal, token)
    return AppointmentRead.model_validate(appointment)


@router.get(
    "",
    response_model=Page[AppointmentRead],
    dependencies=[CanRead],
    summary="Search appointments (RECEPTIONIST, DOCTOR, ADMIN)",
)
def search_appointments(
    db: DbSession,
    clock: CurrentClock,
    patient_id: Annotated[uuid.UUID | None, Query()] = None,
    provider_id: Annotated[uuid.UUID | None, Query()] = None,
    facility_id: Annotated[uuid.UUID | None, Query()] = None,
    date_from: Annotated[
        AwareDatetime | None, Query(description="Appointments ending after this instant (timezone-aware)")
    ] = None,
    date_to: Annotated[
        AwareDatetime | None, Query(description="Appointments starting before this instant (timezone-aware)")
    ] = None,
    status_filter: Annotated[AppointmentStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AppointmentRead]:
    items, total = AppointmentService(db, clock).search(
        patient_id=patient_id,
        provider_id=provider_id,
        facility_id=facility_id,
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[AppointmentRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentRead,
    dependencies=[CanRead],
    responses=_NOT_FOUND,
    summary="Get an appointment (RECEPTIONIST, DOCTOR, ADMIN)",
)
def get_appointment(appointment_id: uuid.UUID, db: DbSession, clock: CurrentClock) -> AppointmentRead:
    return AppointmentRead.model_validate(AppointmentService(db, clock).get(appointment_id))


@router.post(
    "/{appointment_id}/reschedule",
    response_model=AppointmentRead,
    dependencies=[CanBook, BookingEnabled],
    responses={**_NOT_FOUND, **_CONFLICT, **_DISABLED},
    summary="Move a BOOKED appointment to a new time (RECEPTIONIST, ADMIN); requires the current version",
)
def reschedule_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentReschedule,
    db: DbSession,
    clock: CurrentClock,
    token: AccessToken,
    scheduling: SchedulingClientDep,
) -> AppointmentRead:
    service = AppointmentService(db, clock, scheduling=scheduling)
    return AppointmentRead.model_validate(service.reschedule(appointment_id, payload, token))


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentRead,
    dependencies=[CanBook, BookingEnabled],
    responses={**_NOT_FOUND, **_CONFLICT, **_DISABLED},
    summary="Cancel a BOOKED appointment with a reason code (RECEPTIONIST, ADMIN); frees the time",
)
def cancel_appointment(
    appointment_id: uuid.UUID, payload: AppointmentCancel, db: DbSession, clock: CurrentClock
) -> AppointmentRead:
    return AppointmentRead.model_validate(AppointmentService(db, clock).cancel(appointment_id, payload))


OptionalTransition = Annotated[StatusTransition | None, Body()]


def _transition(
    db: DbSession, clock: CurrentClock, appointment_id: uuid.UUID, target: AppointmentStatus, payload
) -> AppointmentRead:
    version = payload.version if payload is not None else None
    return AppointmentRead.model_validate(
        AppointmentService(db, clock).transition(appointment_id, target, version)
    )


@router.post(
    "/{appointment_id}/check-in",
    response_model=AppointmentRead,
    dependencies=[CanTransition],
    responses={**_NOT_FOUND, **_CONFLICT},
    summary="BOOKED -> CHECKED_IN (RECEPTIONIST, DOCTOR, ADMIN)",
)
def check_in_appointment(
    appointment_id: uuid.UUID, db: DbSession, clock: CurrentClock, payload: OptionalTransition = None
) -> AppointmentRead:
    return _transition(db, clock, appointment_id, AppointmentStatus.CHECKED_IN, payload)


@router.post(
    "/{appointment_id}/complete",
    response_model=AppointmentRead,
    dependencies=[CanTransition],
    responses={**_NOT_FOUND, **_CONFLICT},
    summary="CHECKED_IN -> COMPLETED (RECEPTIONIST, DOCTOR, ADMIN)",
)
def complete_appointment(
    appointment_id: uuid.UUID, db: DbSession, clock: CurrentClock, payload: OptionalTransition = None
) -> AppointmentRead:
    return _transition(db, clock, appointment_id, AppointmentStatus.COMPLETED, payload)


@router.post(
    "/{appointment_id}/no-show",
    response_model=AppointmentRead,
    dependencies=[CanTransition],
    responses={**_NOT_FOUND, **_CONFLICT},
    summary="BOOKED -> NO_SHOW (RECEPTIONIST, DOCTOR, ADMIN); frees the time",
)
def no_show_appointment(
    appointment_id: uuid.UUID, db: DbSession, clock: CurrentClock, payload: OptionalTransition = None
) -> AppointmentRead:
    return _transition(db, clock, appointment_id, AppointmentStatus.NO_SHOW, payload)
