import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import AwareDatetime

from app.api.deps import AccessToken, CurrentClock, DbSession, FacilityClientDep, require_permission
from app.domain.roles import Permission
from app.schemas.availability_exception import ExceptionCreate, ExceptionRead, ExceptionUpdate
from app.schemas.common import ErrorResponse, Page
from app.services.availability_exception_service import AvailabilityExceptionService

router = APIRouter(
    tags=["exceptions"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)

CanRead = Depends(require_permission(Permission.SCHEDULE_READ))
CanManage = Depends(require_permission(Permission.EXCEPTIONS_MANAGE))
_NOT_FOUND = {404: {"model": ErrorResponse}}


@router.post(
    "/providers/{provider_id}/exceptions",
    response_model=ExceptionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CanManage],
    responses={**_NOT_FOUND, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    summary="Add leave, a holiday, a block or extra hours (ADMIN, RECEPTIONIST)",
)
def create_exception(
    provider_id: uuid.UUID,
    payload: ExceptionCreate,
    db: DbSession,
    clock: CurrentClock,
    facilities: FacilityClientDep,
    token: AccessToken,
) -> ExceptionRead:
    exception = AvailabilityExceptionService(db, clock, facilities).create(provider_id, payload, token)
    return ExceptionRead.model_validate(exception)


@router.get(
    "/providers/{provider_id}/exceptions",
    response_model=Page[ExceptionRead],
    dependencies=[CanRead],
    summary="List exceptions overlapping a UTC range (any authenticated role)",
)
def list_exceptions(
    provider_id: uuid.UUID,
    db: DbSession,
    clock: CurrentClock,
    range_from: Annotated[AwareDatetime, Query(alias="from", description="Range start (timezone-aware)")],
    range_to: Annotated[
        AwareDatetime, Query(alias="to", description="Range end, exclusive (timezone-aware)")
    ],
    facility_id: Annotated[
        uuid.UUID | None, Query(description="Only exceptions for this facility or for all facilities")
    ] = None,
    active: Annotated[
        bool | None, Query(description="Filter by active status (default: active only)")
    ] = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ExceptionRead]:
    items, total = AvailabilityExceptionService(db, clock).list(
        provider_id,
        range_from=range_from,
        range_to=range_to,
        facility_id=facility_id,
        active=active,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[ExceptionRead.model_validate(item) for item in items], total=total, limit=limit, offset=offset
    )


@router.patch(
    "/exceptions/{exception_id}",
    response_model=ExceptionRead,
    dependencies=[CanManage],
    responses=_NOT_FOUND,
    summary="Update or re-activate an exception (ADMIN, RECEPTIONIST)",
)
def update_exception(
    exception_id: uuid.UUID, payload: ExceptionUpdate, db: DbSession, clock: CurrentClock
) -> ExceptionRead:
    return ExceptionRead.model_validate(AvailabilityExceptionService(db, clock).update(exception_id, payload))


@router.delete(
    "/exceptions/{exception_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[CanManage],
    responses=_NOT_FOUND,
    summary="Deactivate an exception (soft delete, ADMIN, RECEPTIONIST)",
)
def deactivate_exception(exception_id: uuid.UUID, db: DbSession, clock: CurrentClock) -> Response:
    AvailabilityExceptionService(db, clock).deactivate(exception_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
