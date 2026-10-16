import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession, require_permission
from app.domain.roles import Permission
from app.schemas.common import ErrorResponse, Page
from app.schemas.specialty import SpecialtyCreate, SpecialtyRead, SpecialtyUpdate
from app.services.specialty_service import SpecialtyService

router = APIRouter(
    prefix="/specialties",
    tags=["specialties"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)

CanRead = Depends(require_permission(Permission.SPECIALTIES_READ))
CanManage = Depends(require_permission(Permission.SPECIALTIES_MANAGE))


@router.post(
    "",
    response_model=SpecialtyRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CanManage],
    responses={409: {"model": ErrorResponse}},
    summary="Create a specialty (ADMIN)",
)
def create_specialty(payload: SpecialtyCreate, db: DbSession) -> SpecialtyRead:
    return SpecialtyRead.model_validate(SpecialtyService(db).create(payload))


@router.get(
    "",
    response_model=Page[SpecialtyRead],
    dependencies=[CanRead],
    summary="List specialties (any authenticated role)",
)
def list_specialties(
    db: DbSession,
    active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[SpecialtyRead]:
    items, total = SpecialtyService(db).list(active=active, limit=limit, offset=offset)
    return Page(
        items=[SpecialtyRead.model_validate(item) for item in items], total=total, limit=limit, offset=offset
    )


@router.patch(
    "/{specialty_id}",
    response_model=SpecialtyRead,
    dependencies=[CanManage],
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Update or deactivate a specialty (ADMIN)",
)
def update_specialty(specialty_id: uuid.UUID, payload: SpecialtyUpdate, db: DbSession) -> SpecialtyRead:
    return SpecialtyRead.model_validate(SpecialtyService(db).update(specialty_id, payload))
