"""Facility use cases. Business rules live here, not in route handlers."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.domain.facilities import FacilityType, format_utc_offset, to_local
from app.models.facility import Facility
from app.repositories.facility_repository import FacilityRepository
from app.schemas.facility import FacilityCreate, FacilityUpdate
from app.services._base import BaseService, Clock

_DUPLICATE_CODE = "A facility with this code already exists"


@dataclass(frozen=True)
class FacilityLocalTime:
    current_local_time: datetime
    utc_offset: str


class FacilityService(BaseService):
    def __init__(self, session: Session, clock: Clock) -> None:
        super().__init__(session, clock)
        self._facilities = FacilityRepository(session)

    def get(self, facility_id: uuid.UUID) -> Facility:
        facility = self._facilities.get(facility_id)
        if facility is None:
            raise NotFoundError("Facility not found")
        return facility

    def local_time(self, facility: Facility) -> FacilityLocalTime:
        local = to_local(self._now(), facility.timezone)
        return FacilityLocalTime(current_local_time=local, utc_offset=format_utc_offset(local))

    def search(
        self,
        *,
        search: str | None,
        facility_type: FacilityType | None,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Facility], int]:
        return self._facilities.search(
            search=search, facility_type=facility_type, active=active, limit=limit, offset=offset
        )

    def create(self, payload: FacilityCreate) -> Facility:
        if self._facilities.code_exists(payload.code):
            raise ConflictError(_DUPLICATE_CODE)
        now = self._now()
        facility = Facility(**payload.model_dump(mode="json"), is_active=True, created_at=now, updated_at=now)
        self._facilities.add(facility)
        self._commit(_DUPLICATE_CODE)
        return facility

    def update(self, facility_id: uuid.UUID, payload: FacilityUpdate) -> Facility:
        facility = self.get(facility_id)
        changes = payload.model_dump(mode="json", exclude_unset=True)
        for field, value in changes.items():
            setattr(facility, field, value)
        if changes:
            facility.updated_at = self._now()
            self._commit("Facility update conflicts with existing data")
        return facility

    def set_active(self, facility_id: uuid.UUID, *, active: bool) -> Facility:
        # Deliberately does not cascade to departments; their own status is managed separately.
        facility = self.get(facility_id)
        if facility.is_active != active:
            facility.is_active = active
            facility.updated_at = self._now()
            self._commit("Facility status change conflicts with existing data")
        return facility
