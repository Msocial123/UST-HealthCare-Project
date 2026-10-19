import logging
import uuid
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.clients.scheduling_client import SchedulingClient
from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.core.tokens import Principal
from app.domain.appointments import AppointmentStatus, EventType, can_transition
from app.models.appointment import PROVIDER_OVERLAP_CONSTRAINT, Appointment
from app.models.outbox_event import OutboxEvent
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.appointment import AppointmentCancel, AppointmentCreate, AppointmentReschedule
from app.services._base import BaseService, Clock

logger = logging.getLogger(__name__)

OVERLAP_MESSAGE = "The provider already has an appointment that overlaps this time"
STALE_MESSAGE = "Appointment was modified by another request; reload it and retry"
UNAVAILABLE_MESSAGE = "Requested time is outside the provider's advertised availability"
_EXCLUSION_VIOLATION = "23P01"
AGGREGATE_TYPE = "Appointment"


def _is_overlap_violation(exc: IntegrityError) -> bool:
    orig = exc.orig
    return getattr(orig, "sqlstate", None) == _EXCLUSION_VIOLATION or PROVIDER_OVERLAP_CONSTRAINT in str(orig)


class AppointmentService(BaseService):
    def __init__(
        self,
        session: Session,
        clock: Clock,
        *,
        scheduling: SchedulingClient | None = None,
    ) -> None:
        super().__init__(session, clock)
        self._repo = AppointmentRepository(session)
        self._scheduling = scheduling

    # Queries -------------------------------------------------------------------------------------

    def get(self, appointment_id: uuid.UUID) -> Appointment:
        appointment = self._repo.get(appointment_id)
        if appointment is None:
            raise NotFoundError("Appointment not found")
        return appointment

    def search(
        self,
        *,
        patient_id: uuid.UUID | None,
        provider_id: uuid.UUID | None,
        facility_id: uuid.UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
        status: AppointmentStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Appointment], int]:
        if date_from is not None and date_to is not None and date_to <= date_from:
            raise DomainValidationError("date_to must be after date_from")
        return self._repo.search(
            patient_id=patient_id,
            provider_id=provider_id,
            facility_id=facility_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            limit=limit,
            offset=offset,
        )

    # Commands (each one is a single transaction: appointment change + outbox event) ----------------

    def book(self, payload: AppointmentCreate, principal: Principal, access_token: str) -> Appointment:
        now = self._now()
        self._ensure_future(payload.starts_at, now)
        self._advise(
            payload.provider_id, payload.facility_id, payload.starts_at, payload.ends_at, access_token
        )
        self._ensure_slot_free(payload.provider_id, payload.starts_at, payload.ends_at)
        appointment = self._repo.add(
            Appointment(
                id=uuid.uuid4(),
                patient_id=payload.patient_id,
                provider_id=payload.provider_id,
                facility_id=payload.facility_id,
                starts_at=payload.starts_at,
                ends_at=payload.ends_at,
                status=AppointmentStatus.BOOKED.value,
                reason_code=payload.reason_code,
                cancellation_reason=None,
                created_by=principal.subject,
                created_at=now,
                updated_at=now,
            )
        )
        self._save(appointment, EventType.APPOINTMENT_CREATED, now)
        return appointment

    def reschedule(
        self, appointment_id: uuid.UUID, payload: AppointmentReschedule, access_token: str
    ) -> Appointment:
        appointment = self.get(appointment_id)
        self._check_version(appointment, payload.version)
        if appointment.status != AppointmentStatus.BOOKED:
            raise ConflictError(f"Only BOOKED appointments can be rescheduled (status: {appointment.status})")
        now = self._now()
        self._ensure_future(payload.starts_at, now)
        self._advise(
            appointment.provider_id, appointment.facility_id, payload.starts_at, payload.ends_at, access_token
        )
        self._ensure_slot_free(appointment.provider_id, payload.starts_at, payload.ends_at, appointment.id)
        appointment.starts_at = payload.starts_at
        appointment.ends_at = payload.ends_at
        appointment.updated_at = now
        self._save(appointment, EventType.APPOINTMENT_RESCHEDULED, now)
        return appointment

    def cancel(self, appointment_id: uuid.UUID, payload: AppointmentCancel) -> Appointment:
        appointment = self.get(appointment_id)
        self._check_version(appointment, payload.version)
        self._ensure_transition(appointment, AppointmentStatus.CANCELLED)
        now = self._now()
        appointment.status = AppointmentStatus.CANCELLED.value
        appointment.cancellation_reason = payload.cancellation_reason
        appointment.updated_at = now
        self._save(appointment, EventType.APPOINTMENT_CANCELLED, now)
        return appointment

    def transition(
        self, appointment_id: uuid.UUID, target: AppointmentStatus, version: int | None
    ) -> Appointment:
        appointment = self.get(appointment_id)
        self._check_version(appointment, version)
        self._ensure_transition(appointment, target)
        appointment.status = target.value
        appointment.updated_at = self._now()
        self._save(appointment, None, appointment.updated_at)
        return appointment

    # Helpers -------------------------------------------------------------------------------------

    @staticmethod
    def _ensure_future(starts_at: datetime, now: datetime) -> None:
        if starts_at <= now:
            raise DomainValidationError("starts_at must be in the future")

    @staticmethod
    def _check_version(appointment: Appointment, version: int | None) -> None:
        if version is not None and version != appointment.version:
            raise ConflictError(STALE_MESSAGE, details={"current_version": appointment.version})

    @staticmethod
    def _ensure_transition(appointment: Appointment, target: AppointmentStatus) -> None:
        current = AppointmentStatus(appointment.status)
        if not can_transition(current, target):
            raise ConflictError(f"Cannot change appointment status from {current} to {target}")

    def _advise(
        self,
        provider_id: uuid.UUID,
        facility_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        access_token: str,
    ) -> None:
        if self._scheduling is None:
            return
        if not self._scheduling.is_available(provider_id, facility_id, starts_at, ends_at, access_token):
            raise ConflictError(UNAVAILABLE_MESSAGE)

    def _ensure_slot_free(
        self,
        provider_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        if self._repo.find_overlapping(provider_id, starts_at, ends_at, exclude_id) is not None:
            raise ConflictError(OVERLAP_MESSAGE)

    def _save(self, appointment: Appointment, event_type: EventType | None, now: datetime) -> None:
        """Flush the change (DB constraints and version check run here), add the outbox row, commit."""
        try:
            self._session.flush()
            if event_type is not None:
                self._repo.add_event(self._event(appointment, event_type, now))
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            if _is_overlap_violation(exc):
                logger.info("booking_conflict", extra={"event": "booking_conflict", "source": "constraint"})
                raise ConflictError(OVERLAP_MESSAGE) from None
            raise
        except StaleDataError:
            self._session.rollback()
            raise ConflictError(STALE_MESSAGE) from None
        except Exception:
            self._session.rollback()
            raise

    @staticmethod
    def _event(appointment: Appointment, event_type: EventType, now: datetime) -> OutboxEvent:
        # IDs, times and status only: no reason codes, patient details or clinical data.
        return OutboxEvent(
            id=uuid.uuid4(),
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id=appointment.id,
            event_type=event_type.value,
            payload={
                "event_type": event_type.value,
                "appointment_id": str(appointment.id),
                "patient_id": str(appointment.patient_id),
                "provider_id": str(appointment.provider_id),
                "facility_id": str(appointment.facility_id),
                "starts_at": appointment.starts_at.isoformat(),
                "ends_at": appointment.ends_at.isoformat(),
                "status": appointment.status,
                "version": appointment.version,
                "occurred_at": now.isoformat(),
            },
            occurred_at=now,
            published_at=None,
        )
