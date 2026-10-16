import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentClock, DbSession, require_permission
from app.domain.facilities import FacilityType
from app.domain.roles import Permission
from app.schemas.common import ErrorResponse, Page
from app.schemas.department import DepartmentCreate, DepartmentRead
from app.schemas.facility import FacilityCreate, FacilityDetail, FacilityRead, FacilityUpdate
from app.services.department_service import DepartmentService
from app.services.facility_service import FacilityService

router = APIRouter(
    prefix="/facilities",
    tags=["facilities"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)

CanRead = Depends(require_permission(Permission.FACILITIES_READ))
CanManage = Depends(require_permission(Permission.FACILITIES_MANAGE))
_NOT_FOUND = {404: {"model": ErrorResponse}}
_CONFLICT = {409: {"model": ErrorResponse}}
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
Active = Annotated[bool | None, Query(description="Filter by active status")]


@router.post(
    "",
    response_model=FacilityRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CanManage],
    responses=_CONFLICT,
    summary="Create a facility (ADMIN)",
)
def create_facility(payload: FacilityCreate, db: DbSession, clock: CurrentClock) -> FacilityRead:
    return FacilityRead.model_validate(FacilityService(db, clock).create(payload))


@router.get(
    "",
    response_model=Page[FacilityRead],
    dependencies=[CanRead],
    summary="List/search facilities by name, code or city (any authenticated role)",
)
def search_facilities(
    db: DbSession,
    clock: CurrentClock,
    search: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=100,
            pattern=r"\S",
            description="Substring of name, code or city (must contain a non-space character)",
        ),
    ] = None,
    type: Annotated[FacilityType | None, Query(description="Filter by facility type")] = None,  # noqa: A002
    active: Active = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[FacilityRead]:
    items, total = FacilityService(db, clock).search(
        search=search.strip() if search else None,
        facility_type=type,
        active=active,
        limit=limit,
        offset=offset,
    )
    return Page[FacilityRead](
        items=[FacilityRead.model_validate(item) for item in items], total=total, limit=limit, offset=offset
    )


@router.get(
    "/{facility_id}",
    response_model=FacilityDetail,
    dependencies=[CanRead],
    responses=_NOT_FOUND,
    summary="Get a facility with its timezone and current local time (any authenticated role)",
)
def get_facility(facility_id: uuid.UUID, db: DbSession, clock: CurrentClock) -> FacilityDetail:
    service = FacilityService(db, clock)
    facility = service.get(facility_id)
    local = service.local_time(facility)
    return FacilityDetail(
        **FacilityRead.model_validate(facility).model_dump(),
        current_local_time=local.current_local_time,
        utc_offset=local.utc_offset,
    )


@router.patch(
    "/{facility_id}",
    response_model=FacilityRead,
    dependencies=[CanManage],
    responses={**_NOT_FOUND, **_CONFLICT},
    summary="Update a facility, including its timezone (ADMIN)",
)
def update_facility(
    facility_id: uuid.UUID, payload: FacilityUpdate, db: DbSession, clock: CurrentClock
) -> FacilityRead:
    return FacilityRead.model_validate(FacilityService(db, clock).update(facility_id, payload))


@router.post(
    "/{facility_id}/deactivate",
    response_model=FacilityRead,
    dependencies=[CanManage],
    responses=_NOT_FOUND,
    summary="Deactivate a facility; never hard-deletes (ADMIN)",
)
def deactivate_facility(facility_id: uuid.UUID, db: DbSession, clock: CurrentClock) -> FacilityRead:
    return FacilityRead.model_validate(FacilityService(db, clock).set_active(facility_id, active=False))


@router.post(
    "/{facility_id}/activate",
    response_model=FacilityRead,
    dependencies=[CanManage],
    responses=_NOT_FOUND,
    summary="Re-activate a facility (ADMIN)",
)
def activate_facility(facility_id: uuid.UUID, db: DbSession, clock: CurrentClock) -> FacilityRead:
    return FacilityRead.model_validate(FacilityService(db, clock).set_active(facility_id, active=True))


@router.post(
    "/{facility_id}/departments",
    response_model=DepartmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CanManage],
    responses={**_NOT_FOUND, **_CONFLICT},
    summary="Create a department in an active facility (ADMIN)",
    tags=["departments"],
)
def create_department(
    facility_id: uuid.UUID, payload: DepartmentCreate, db: DbSession, clock: CurrentClock
) -> DepartmentRead:
    return DepartmentRead.model_validate(DepartmentService(db, clock).create(facility_id, payload))


@router.get(
    "/{facility_id}/departments",
    response_model=Page[DepartmentRead],
    dependencies=[CanRead],
    responses=_NOT_FOUND,
    summary="List departments of a facility (any authenticated role)",
    tags=["departments"],
)
def list_departments(
    facility_id: uuid.UUID,
    db: DbSession,
    clock: CurrentClock,
    active: Active = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[DepartmentRead]:
    items, total = DepartmentService(db, clock).list_for_facility(
        facility_id, active=active, limit=limit, offset=offset
    )
    return Page[DepartmentRead](
        items=[DepartmentRead.model_validate(item) for item in items], total=total, limit=limit, offset=offset
    )
