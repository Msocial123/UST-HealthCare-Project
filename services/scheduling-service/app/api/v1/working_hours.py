import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import AccessToken, CurrentClock, DbSession, FacilityClientDep, require_permission
from app.domain.roles import Permission
from app.schemas.common import ErrorResponse, Page
from app.schemas.working_hours import WorkingHoursCreate, WorkingHoursRead, WorkingHoursUpdate
from app.services.working_hours_service import WorkingHoursService

router = APIRouter(
    tags=["working-hours"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)

CanRead = Depends(require_permission(Permission.SCHEDULE_READ))
CanManage = Depends(require_permission(Permission.WORKING_HOURS_MANAGE))
_NOT_FOUND = {404: {"model": ErrorResponse}}
_CONFLICT = {409: {"model": ErrorResponse}}
_UNAVAILABLE = {503: {"model": ErrorResponse}}


@router.post(
    "/providers/{provider_id}/working-hours",
    response_model=WorkingHoursRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CanManage],
    responses={**_NOT_FOUND, **_CONFLICT, **_UNAVAILABLE},
    summary="Add a weekly working-hours rule in facility-local time (ADMIN)",
)
def create_working_hours(
    provider_id: uuid.UUID,
    payload: WorkingHoursCreate,
    db: DbSession,
    clock: CurrentClock,
    facilities: FacilityClientDep,
    token: AccessToken,
) -> WorkingHoursRead:
    rule = WorkingHoursService(db, clock, facilities).create(provider_id, payload, token)
    return WorkingHoursRead.model_validate(rule)


@router.get(
    "/providers/{provider_id}/working-hours",
    response_model=Page[WorkingHoursRead],
    dependencies=[CanRead],
    summary="List a provider's working-hours rules (any authenticated role)",
)
def list_working_hours(
    provider_id: uuid.UUID,
    db: DbSession,
    clock: CurrentClock,
    facility_id: Annotated[uuid.UUID | None, Query(description="Filter by facility")] = None,
    weekday: Annotated[int | None, Query(ge=0, le=6, description="0 = Monday ... 6 = Sunday")] = None,
    active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[WorkingHoursRead]:
    items, total = WorkingHoursService(db, clock).list(
        provider_id, facility_id=facility_id, weekday=weekday, active=active, limit=limit, offset=offset
    )
    return Page(
        items=[WorkingHoursRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/working-hours/{working_hours_id}",
    response_model=WorkingHoursRead,
    dependencies=[CanManage],
    responses={**_NOT_FOUND, **_CONFLICT},
    summary="Update or re-activate a working-hours rule (ADMIN)",
)
def update_working_hours(
    working_hours_id: uuid.UUID, payload: WorkingHoursUpdate, db: DbSession, clock: CurrentClock
) -> WorkingHoursRead:
    return WorkingHoursRead.model_validate(WorkingHoursService(db, clock).update(working_hours_id, payload))


@router.delete(
    "/working-hours/{working_hours_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[CanManage],
    responses=_NOT_FOUND,
    summary="Deactivate a working-hours rule (soft delete, ADMIN)",
)
def deactivate_working_hours(working_hours_id: uuid.UUID, db: DbSession, clock: CurrentClock) -> Response:
    WorkingHoursService(db, clock).deactivate(working_hours_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
