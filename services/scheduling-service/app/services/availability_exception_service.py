import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.clients.facility_client import FacilityClient
from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.domain.scheduling import MAX_EXCEPTION_RANGE_DAYS, ExceptionType, exception_problem
from app.models.availability_exception import AvailabilityException
from app.repositories.availability_exception_repository import AvailabilityExceptionRepository
from app.schemas.availability_exception import ExceptionCreate, ExceptionUpdate
from app.services._base import BaseService, Clock

_CONFLICT = "Availability exception could not be saved"


class AvailabilityExceptionService(BaseService):
    def __init__(self, session: Session, clock: Clock, facilities: FacilityClient | None = None) -> None:
        super().__init__(session, clock)
        self._repo = AvailabilityExceptionRepository(session)
        self._facilities = facilities

    def create(
        self, provider_id: uuid.UUID, payload: ExceptionCreate, access_token: str
    ) -> AvailabilityException:
        if payload.facility_id is not None:
            if self._facilities is None:
                raise RuntimeError("a FacilityClient is required for facility-specific exceptions")
            facility = self._facilities.get_facility(payload.facility_id, access_token)
            if payload.type == ExceptionType.EXTRA_HOURS and not facility.is_active:
                raise ConflictError("Facility is inactive")
        now = self._now()
        exception = self._repo.add(
            AvailabilityException(
                provider_id=provider_id,
                facility_id=payload.facility_id,
                starts_at=payload.starts_at,
                ends_at=payload.ends_at,
                type=payload.type.value,
                reason_code=payload.reason_code,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        self._commit(_CONFLICT)
        return exception

    def get(self, exception_id: uuid.UUID) -> AvailabilityException:
        exception = self._repo.get(exception_id)
        if exception is None:
            raise NotFoundError("Availability exception not found")
        return exception

    def list(
        self,
        provider_id: uuid.UUID,
        *,
        range_from: datetime,
        range_to: datetime,
        facility_id: uuid.UUID | None,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AvailabilityException], int]:
        if range_to <= range_from:
            raise DomainValidationError("'to' must be after 'from'")
        if range_to - range_from > timedelta(days=MAX_EXCEPTION_RANGE_DAYS):
            raise DomainValidationError(f"The range may span at most {MAX_EXCEPTION_RANGE_DAYS} days")
        return self._repo.list_overlapping(
            provider_id,
            starts_before=range_to,
            ends_after=range_from,
            facility_id=facility_id,
            active=active,
            limit=limit,
            offset=offset,
        )

    def update(self, exception_id: uuid.UUID, payload: ExceptionUpdate) -> AvailabilityException:
        exception = self.get(exception_id)
        changes = payload.model_dump(exclude_unset=True)
        starts_at = changes.get("starts_at", exception.starts_at)
        ends_at = changes.get("ends_at", exception.ends_at)
        exception_type = ExceptionType(changes.get("type", exception.type))
        problem = exception_problem(starts_at, ends_at, exception_type, exception.facility_id is not None)
        if problem:
            raise DomainValidationError(problem)
        for field, value in changes.items():
            setattr(exception, field, value.value if isinstance(value, ExceptionType) else value)
        exception.updated_at = self._now()
        self._commit(_CONFLICT)
        return exception

    def deactivate(self, exception_id: uuid.UUID) -> AvailabilityException:
        exception = self.get(exception_id)
        if exception.is_active:
            exception.is_active = False
            exception.updated_at = self._now()
            self._commit(_CONFLICT)
        return exception
