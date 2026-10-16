import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.availability_exception import AvailabilityException


class AvailabilityExceptionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, exception_id: uuid.UUID) -> AvailabilityException | None:
        return self._session.get(AvailabilityException, exception_id)

    def add(self, exception: AvailabilityException) -> AvailabilityException:
        self._session.add(exception)
        return exception

    def list_overlapping(
        self,
        provider_id: uuid.UUID,
        *,
        starts_before: datetime,
        ends_after: datetime,
        facility_id: uuid.UUID | None,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AvailabilityException], int]:
        stmt = select(AvailabilityException).where(
            AvailabilityException.provider_id == provider_id,
            AvailabilityException.starts_at < starts_before,
            AvailabilityException.ends_at > ends_after,
        )
        if facility_id is not None:
            stmt = stmt.where(
                or_(
                    AvailabilityException.facility_id.is_(None),
                    AvailabilityException.facility_id == facility_id,
                )
            )
        if active is not None:
            stmt = stmt.where(AvailabilityException.is_active.is_(active))
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        ordered = stmt.order_by(AvailabilityException.starts_at, AvailabilityException.id)
        return list(self._session.scalars(ordered.limit(limit).offset(offset)).all()), total

    def active_for_slots(
        self,
        provider_id: uuid.UUID,
        facility_id: uuid.UUID,
        *,
        starts_before: datetime,
        ends_after: datetime,
        types: Collection[str],
    ) -> list[AvailabilityException]:
        stmt = select(AvailabilityException).where(
            AvailabilityException.provider_id == provider_id,
            AvailabilityException.is_active.is_(True),
            AvailabilityException.type.in_(list(types)),
            AvailabilityException.starts_at < starts_before,
            AvailabilityException.ends_at > ends_after,
            or_(
                AvailabilityException.facility_id.is_(None), AvailabilityException.facility_id == facility_id
            ),
        )
        return list(self._session.scalars(stmt).all())
