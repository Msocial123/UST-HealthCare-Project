import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentClock, DbSession, require_permission
from app.domain.roles import Permission
from app.schemas.common import ErrorResponse, Page
from app.schemas.department import DepartmentRead, DepartmentUpdate
from app.schemas.room import RoomCreate, RoomRead
from app.services.department_service import DepartmentService
from app.services.room_service import RoomService

router = APIRouter(
    prefix="/departments",
    tags=["departments"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)

CanRead = Depends(require_permission(Permission.FACILITIES_READ))
CanManage = Depends(require_permission(Permission.FACILITIES_MANAGE))
_CONFLICT = {409: {"model": ErrorResponse}}


@router.get(
    "/{department_id}",
    response_model=DepartmentRead,
    dependencies=[CanRead],
    summary="Get a department (any authenticated role)",
)
def get_department(department_id: uuid.UUID, db: DbSession, clock: CurrentClock) -> DepartmentRead:
    return DepartmentRead.model_validate(DepartmentService(db, clock).get(department_id))


@router.patch(
    "/{department_id}",
    response_model=DepartmentRead,
    dependencies=[CanManage],
    responses=_CONFLICT,
    summary="Update, deactivate or re-activate a department (ADMIN)",
)
def update_department(
    department_id: uuid.UUID, payload: DepartmentUpdate, db: DbSession, clock: CurrentClock
) -> DepartmentRead:
    return DepartmentRead.model_validate(DepartmentService(db, clock).update(department_id, payload))


@router.post(
    "/{department_id}/rooms",
    response_model=RoomRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CanManage],
    responses=_CONFLICT,
    summary="Create a room in an active department (ADMIN)",
    tags=["rooms"],
)
def create_room(
    department_id: uuid.UUID, payload: RoomCreate, db: DbSession, clock: CurrentClock
) -> RoomRead:
    return RoomRead.model_validate(RoomService(db, clock).create(department_id, payload))


@router.get(
    "/{department_id}/rooms",
    response_model=Page[RoomRead],
    dependencies=[CanRead],
    summary="List rooms of a department (any authenticated role)",
    tags=["rooms"],
)
def list_rooms(
    department_id: uuid.UUID,
    db: DbSession,
    clock: CurrentClock,
    active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RoomRead]:
    items, total = RoomService(db, clock).list_for_department(
        department_id, active=active, limit=limit, offset=offset
    )
    return Page[RoomRead](
        items=[RoomRead.model_validate(item) for item in items], total=total, limit=limit, offset=offset
    )
