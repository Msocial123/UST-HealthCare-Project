import uuid
from datetime import date, time

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.models.working_hours import WorkingHours


class WorkingHoursRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, working_hours_id: uuid.UUID) -> WorkingHours | None:
        return self._session.get(WorkingHours, working_hours_id)

    def add(self, rule: WorkingHours) -> WorkingHours:
        self._session.add(rule)
        return rule

    def lock_provider(self, provider_id: uuid.UUID) -> None:
        """Serialise rule writes per provider so the overlap pre-check cannot race (PostgreSQL only)."""
        if self._session.get_bind().dialect.name == "postgresql":
            key = int.from_bytes(provider_id.bytes[:8], "big", signed=True)
            self._session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

    def find_overlapping(
        self,
        *,
        provider_id: uuid.UUID,
        facility_id: uuid.UUID,
        weekday: int,
        start: time,
        end: time,
        valid_from: date,
        valid_to: date | None,
        exclude_id: uuid.UUID | None = None,
    ) -> WorkingHours | None:
        stmt = select(WorkingHours).where(
            WorkingHours.provider_id == provider_id,
            WorkingHours.facility_id == facility_id,
            WorkingHours.weekday == weekday,
            WorkingHours.is_active.is_(True),
            WorkingHours.start_local_time < end,
            WorkingHours.end_local_time > start,
            or_(WorkingHours.valid_to.is_(None), WorkingHours.valid_to >= valid_from),
        )
        if valid_to is not None:
            stmt = stmt.where(WorkingHours.valid_from <= valid_to)
        if exclude_id is not None:
            stmt = stmt.where(WorkingHours.id != exclude_id)
        return self._session.scalars(stmt.limit(1)).first()

    def list_for_provider(
        self,
        provider_id: uuid.UUID,
        *,
        facility_id: uuid.UUID | None,
        weekday: int | None,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkingHours], int]:
        stmt = select(WorkingHours).where(WorkingHours.provider_id == provider_id)
        if facility_id is not None:
            stmt = stmt.where(WorkingHours.facility_id == facility_id)
        if weekday is not None:
            stmt = stmt.where(WorkingHours.weekday == weekday)
        if active is not None:
            stmt = stmt.where(WorkingHours.is_active.is_(active))
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        ordered = stmt.order_by(
            WorkingHours.weekday, WorkingHours.start_local_time, WorkingHours.valid_from, WorkingHours.id
        )
        return list(self._session.scalars(ordered.limit(limit).offset(offset)).all()), total

    def active_rules_in_range(
        self, provider_id: uuid.UUID, facility_id: uuid.UUID, date_from: date, date_to: date
    ) -> list[WorkingHours]:
        stmt = select(WorkingHours).where(
            WorkingHours.provider_id == provider_id,
            WorkingHours.facility_id == facility_id,
            WorkingHours.is_active.is_(True),
            WorkingHours.valid_from <= date_to,
            or_(WorkingHours.valid_to.is_(None), WorkingHours.valid_to >= date_from),
        )
        return list(self._session.scalars(stmt).all())
