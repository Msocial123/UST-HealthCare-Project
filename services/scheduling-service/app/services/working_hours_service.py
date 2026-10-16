import uuid
from datetime import date, time

from sqlalchemy.orm import Session

from app.clients.facility_client import FacilityClient
from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.domain.scheduling import working_hours_problem
from app.models.working_hours import WorkingHours
from app.repositories.working_hours_repository import WorkingHoursRepository
from app.schemas.working_hours import WorkingHoursCreate, WorkingHoursUpdate
from app.services._base import BaseService, Clock

OVERLAP_MESSAGE = "An active working-hours rule for this provider, facility and weekday overlaps this one"


class WorkingHoursService(BaseService):
    def __init__(self, session: Session, clock: Clock, facilities: FacilityClient | None = None) -> None:
        super().__init__(session, clock)
        self._repo = WorkingHoursRepository(session)
        self._facilities = facilities

    def create(self, provider_id: uuid.UUID, payload: WorkingHoursCreate, access_token: str) -> WorkingHours:
        if self._facilities is None:
            raise RuntimeError("a FacilityClient is required to create working hours")
        facility = self._facilities.get_facility(payload.facility_id, access_token)
        if not facility.is_active:
            raise ConflictError("Facility is inactive")

        self._repo.lock_provider(provider_id)
        self._ensure_no_overlap(
            provider_id,
            payload.facility_id,
            payload.weekday,
            payload.start_local_time,
            payload.end_local_time,
            payload.valid_from,
            payload.valid_to,
        )
        now = self._now()
        rule = self._repo.add(
            WorkingHours(
                provider_id=provider_id,
                facility_id=payload.facility_id,
                weekday=payload.weekday,
                start_local_time=payload.start_local_time,
                end_local_time=payload.end_local_time,
                slot_minutes=payload.slot_minutes,
                valid_from=payload.valid_from,
                valid_to=payload.valid_to,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        self._commit(OVERLAP_MESSAGE)
        return rule

    def get(self, working_hours_id: uuid.UUID) -> WorkingHours:
        rule = self._repo.get(working_hours_id)
        if rule is None:
            raise NotFoundError("Working-hours rule not found")
        return rule

    def list(
        self,
        provider_id: uuid.UUID,
        *,
        facility_id: uuid.UUID | None,
        weekday: int | None,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkingHours], int]:
        return self._repo.list_for_provider(
            provider_id, facility_id=facility_id, weekday=weekday, active=active, limit=limit, offset=offset
        )

    def update(self, working_hours_id: uuid.UUID, payload: WorkingHoursUpdate) -> WorkingHours:
        rule = self._get_locked(working_hours_id)
        changes = payload.model_dump(exclude_unset=True)
        merged = {
            field: changes.get(field, getattr(rule, field))
            for field in (
                "weekday",
                "start_local_time",
                "end_local_time",
                "slot_minutes",
                "valid_from",
                "valid_to",
                "is_active",
            )
        }
        problem = working_hours_problem(
            merged["start_local_time"],
            merged["end_local_time"],
            merged["slot_minutes"],
            merged["valid_from"],
            merged["valid_to"],
        )
        if problem:
            raise DomainValidationError(problem)
        if merged["is_active"]:
            self._ensure_no_overlap(
                rule.provider_id,
                rule.facility_id,
                merged["weekday"],
                merged["start_local_time"],
                merged["end_local_time"],
                merged["valid_from"],
                merged["valid_to"],
                exclude_id=rule.id,
            )
        for field, value in changes.items():
            setattr(rule, field, value)
        rule.updated_at = self._now()
        self._commit(OVERLAP_MESSAGE)
        return rule

    def deactivate(self, working_hours_id: uuid.UUID) -> WorkingHours:
        rule = self._get_locked(working_hours_id)
        if rule.is_active:
            rule.is_active = False
            rule.updated_at = self._now()
            self._commit(OVERLAP_MESSAGE)
        return rule

    def _get_locked(self, working_hours_id: uuid.UUID) -> WorkingHours:
        """Load the rule, lock its provider, then re-read it so validation never uses stale values."""
        rule = self.get(working_hours_id)
        self._repo.lock_provider(rule.provider_id)
        self._session.refresh(rule)
        return rule

    def _ensure_no_overlap(
        self,
        provider_id: uuid.UUID,
        facility_id: uuid.UUID,
        weekday: int,
        start: time,
        end: time,
        valid_from: date,
        valid_to: date | None,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        overlapping = self._repo.find_overlapping(
            provider_id=provider_id,
            facility_id=facility_id,
            weekday=weekday,
            start=start,
            end=end,
            valid_from=valid_from,
            valid_to=valid_to,
            exclude_id=exclude_id,
        )
        if overlapping is not None:
            self._session.rollback()
            raise ConflictError(OVERLAP_MESSAGE, details={"conflicting_id": str(overlapping.id)})
