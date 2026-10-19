import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.appointments import SLOT_OCCUPYING_STATUSES, AppointmentStatus
from app.models.appointment import Appointment
from app.models.outbox_event import OutboxEvent

_OCCUPYING = [status.value for status in SLOT_OCCUPYING_STATUSES]


class AppointmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, appointment_id: uuid.UUID) -> Appointment | None:
        return self._session.get(Appointment, appointment_id)

    def add(self, appointment: Appointment) -> Appointment:
        self._session.add(appointment)
        return appointment

    def add_event(self, outbox_event: OutboxEvent) -> OutboxEvent:
        self._session.add(outbox_event)
        return outbox_event

    def find_overlapping(
        self,
        provider_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_id: uuid.UUID | None = None,
    ) -> Appointment | None:
        """Pre-check only (friendly error, and the only check on SQLite); the DB constraint is final."""
        stmt = select(Appointment).where(
            Appointment.provider_id == provider_id,
            Appointment.status.in_(_OCCUPYING),
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
        )
        if exclude_id is not None:
            stmt = stmt.where(Appointment.id != exclude_id)
        return self._session.scalars(stmt.limit(1)).first()

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
        stmt = select(Appointment)
        if patient_id is not None:
            stmt = stmt.where(Appointment.patient_id == patient_id)
        if provider_id is not None:
            stmt = stmt.where(Appointment.provider_id == provider_id)
        if facility_id is not None:
            stmt = stmt.where(Appointment.facility_id == facility_id)
        if date_from is not None:
            stmt = stmt.where(Appointment.ends_at > date_from)
        if date_to is not None:
            stmt = stmt.where(Appointment.starts_at < date_to)
        if status is not None:
            stmt = stmt.where(Appointment.status == status.value)
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        ordered = stmt.order_by(Appointment.starts_at, Appointment.id)
        return list(self._session.scalars(ordered.limit(limit).offset(offset)).all()), total
