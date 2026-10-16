import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession, require_permission
from app.domain.roles import Permission
from app.schemas.common import ErrorResponse, Page
from app.schemas.provider import ProviderCreate, ProviderRead, ProviderUpdate
from app.services.provider_service import ProviderService

router = APIRouter(
    prefix="/providers",
    tags=["providers"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)

CanRead = Depends(require_permission(Permission.PROVIDERS_READ))
CanManage = Depends(require_permission(Permission.PROVIDERS_MANAGE))
_NOT_FOUND = {404: {"model": ErrorResponse}}
_CONFLICT = {409: {"model": ErrorResponse}}


@router.post(
    "",
    response_model=ProviderRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CanManage],
    responses={**_NOT_FOUND, **_CONFLICT},
    summary="Create a provider with specialties (ADMIN)",
)
def create_provider(payload: ProviderCreate, db: DbSession) -> ProviderRead:
    return ProviderRead.from_model(ProviderService(db).create(payload))


@router.get(
    "",
    response_model=Page[ProviderRead],
    dependencies=[CanRead],
    summary="Search providers by name, provider number or specialty code (RECEPTIONIST, DOCTOR, ADMIN)",
)
def search_providers(
    db: DbSession,
    search: Annotated[
        str | None, Query(min_length=1, max_length=100, description="Name, provider number or specialty code")
    ] = None,
    specialty: Annotated[
        str | None,
        Query(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_]+$", description="Exact specialty code"),
    ] = None,
    active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ProviderRead]:
    items, total = ProviderService(db).search(
        search=search.strip() if search else None,
        specialty_code=specialty.upper() if specialty else None,
        active=active,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[ProviderRead.from_model(item) for item in items], total=total, limit=limit, offset=offset
    )


@router.get(
    "/{provider_id}",
    response_model=ProviderRead,
    dependencies=[CanRead],
    responses=_NOT_FOUND,
    summary="Get a provider with specialties (RECEPTIONIST, DOCTOR, ADMIN)",
)
def get_provider(provider_id: uuid.UUID, db: DbSession) -> ProviderRead:
    return ProviderRead.from_model(ProviderService(db).get(provider_id))


@router.patch(
    "/{provider_id}",
    response_model=ProviderRead,
    dependencies=[CanManage],
    responses={**_NOT_FOUND, **_CONFLICT},
    summary="Update a provider profile and specialties (ADMIN)",
)
def update_provider(provider_id: uuid.UUID, payload: ProviderUpdate, db: DbSession) -> ProviderRead:
    return ProviderRead.from_model(ProviderService(db).update(provider_id, payload))


@router.post(
    "/{provider_id}/deactivate",
    response_model=ProviderRead,
    dependencies=[CanManage],
    responses=_NOT_FOUND,
    summary="Deactivate a provider; never hard-deletes (ADMIN)",
)
def deactivate_provider(provider_id: uuid.UUID, db: DbSession) -> ProviderRead:
    return ProviderRead.from_model(ProviderService(db).set_active(provider_id, active=False))


@router.post(
    "/{provider_id}/activate",
    response_model=ProviderRead,
    dependencies=[CanManage],
    responses=_NOT_FOUND,
    summary="Re-activate a provider (ADMIN)",
)
def activate_provider(provider_id: uuid.UUID, db: DbSession) -> ProviderRead:
    return ProviderRead.from_model(ProviderService(db).set_active(provider_id, active=True))
