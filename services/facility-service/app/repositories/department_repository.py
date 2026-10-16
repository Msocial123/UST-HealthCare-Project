import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import Department


class DepartmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, department_id: uuid.UUID) -> Department | None:
        return self._session.get(Department, department_id)

    def code_exists(self, facility_id: uuid.UUID, code: str) -> bool:
        stmt = select(Department.id).where(Department.facility_id == facility_id, Department.code == code)
        return self._session.scalar(stmt) is not None

    def list_for_facility(
        self, facility_id: uuid.UUID, *, active: bool | None, limit: int, offset: int
    ) -> tuple[list[Department], int]:
        stmt = select(Department).where(Department.facility_id == facility_id)
        if active is not None:
            stmt = stmt.where(Department.is_active.is_(active))
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        ordered = stmt.order_by(Department.code)
        return list(self._session.scalars(ordered.limit(limit).offset(offset)).all()), total

    def add(self, department: Department) -> Department:
        self._session.add(department)
        return department
