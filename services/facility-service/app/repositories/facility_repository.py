import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domain.facilities import FacilityType
from app.models.facility import Facility
from app.repositories._common import escape_like


class FacilityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, facility_id: uuid.UUID) -> Facility | None:
        return self._session.get(Facility, facility_id)

    def code_exists(self, code: str) -> bool:
        return self._session.scalar(select(Facility.id).where(Facility.code == code)) is not None

    def search(
        self,
        *,
        search: str | None,
        facility_type: FacilityType | None,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Facility], int]:
        stmt = select(Facility)
        if search:
            pattern = f"%{escape_like(search.lower())}%"
            stmt = stmt.where(
                or_(
                    func.lower(Facility.name).like(pattern, escape="\\"),
                    func.lower(Facility.code).like(pattern, escape="\\"),
                    func.lower(Facility.city).like(pattern, escape="\\"),
                )
            )
        if facility_type is not None:
            stmt = stmt.where(Facility.facility_type == facility_type.value)
        if active is not None:
            stmt = stmt.where(Facility.is_active.is_(active))
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        ordered = stmt.order_by(Facility.name, Facility.code)
        return list(self._session.scalars(ordered.limit(limit).offset(offset)).all()), total

    def add(self, facility: Facility) -> Facility:
        self._session.add(facility)
        return facility
