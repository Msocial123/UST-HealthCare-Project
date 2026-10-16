"""Advisory slot queries. Read-only: nothing is reserved, locked or written."""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.clients.facility_client import FacilityClient, FacilityInfo
from app.core.errors import ConflictError, DomainValidationError
from app.domain.scheduling import BLOCKING_EXCEPTION_TYPES, MAX_SLOT_RANGE_DAYS, ExceptionType
from app.domain.slots import Slot, WeeklyRule, Window, compute_slots, local_day_bounds
from app.repositories.availability_exception_repository import AvailabilityExceptionRepository
from app.repositories.working_hours_repository import WorkingHoursRepository
from app.services._base import BaseService, Clock


@dataclass(frozen=True)
class SlotQueryResult:
    facility: FacilityInfo
    slots: list[Slot]


class SlotService(BaseService):
    def __init__(
        self, session: Session, clock: Clock, facilities: FacilityClient, *, extra_slot_minutes: int
    ) -> None:
        super().__init__(session, clock)
        self._rules = WorkingHoursRepository(session)
        self._exceptions = AvailabilityExceptionRepository(session)
        self._facilities = facilities
        self._extra_slot_minutes = extra_slot_minutes

    def query(
        self,
        provider_id: uuid.UUID,
        facility_id: uuid.UUID,
        date_from: date,
        date_to: date,
        access_token: str,
    ) -> SlotQueryResult:
        if date_to < date_from:
            raise DomainValidationError("date_to must be on or after date_from")
        if (date_to - date_from).days + 1 > MAX_SLOT_RANGE_DAYS:
            raise DomainValidationError(f"The date range may span at most {MAX_SLOT_RANGE_DAYS} days")

        facility = self._facilities.get_facility(facility_id, access_token)
        if not facility.is_active:
            raise ConflictError("Facility is inactive")
        zone = facility.zone
        bounds = local_day_bounds(date_from, date_to, zone)

        rules = [
            WeeklyRule(
                weekday=rule.weekday,
                start_local_time=rule.start_local_time,
                end_local_time=rule.end_local_time,
                slot_minutes=rule.slot_minutes,
                valid_from=rule.valid_from,
                valid_to=rule.valid_to,
            )
            for rule in self._rules.active_rules_in_range(provider_id, facility_id, date_from, date_to)
        ]
        exceptions = self._exceptions.active_for_slots(
            provider_id,
            facility_id,
            starts_before=bounds.ends_at,
            ends_after=bounds.starts_at,
            types=[member.value for member in ExceptionType],
        )
        extra = [
            Window(item.starts_at, item.ends_at)
            for item in exceptions
            if item.type == ExceptionType.EXTRA_HOURS and item.facility_id == facility_id
        ]
        blocks = [
            Window(item.starts_at, item.ends_at)
            for item in exceptions
            if item.type in BLOCKING_EXCEPTION_TYPES
        ]
        slots = compute_slots(
            rules=rules,
            extra_windows=extra,
            blocks=blocks,
            zone=zone,
            date_from=date_from,
            date_to=date_to,
            extra_slot_minutes=self._extra_slot_minutes,
        )
        return SlotQueryResult(facility=facility, slots=slots)
