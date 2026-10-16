"""Department use cases."""

import uuid

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.department import Department
from app.repositories.department_repository import DepartmentRepository
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services._base import BaseService, Clock
from app.services.facility_service import FacilityService

_DUPLICATE_CODE = "A department with this code already exists in this facility"


class DepartmentService(BaseService):
    def __init__(self, session: Session, clock: Clock) -> None:
        super().__init__(session, clock)
        self._departments = DepartmentRepository(session)
        self._facilities = FacilityService(session, clock)

    def get(self, department_id: uuid.UUID) -> Department:
        department = self._departments.get(department_id)
        if department is None:
            raise NotFoundError("Department not found")
        return department

    def list_for_facility(
        self, facility_id: uuid.UUID, *, active: bool | None, limit: int, offset: int
    ) -> tuple[list[Department], int]:
        self._facilities.get(facility_id)
        return self._departments.list_for_facility(facility_id, active=active, limit=limit, offset=offset)

    def create(self, facility_id: uuid.UUID, payload: DepartmentCreate) -> Department:
        facility = self._facilities.get(facility_id)
        if not facility.is_active:
            raise ConflictError("Departments cannot be created in an inactive facility")
        if self._departments.code_exists(facility.id, payload.code):
            raise ConflictError(_DUPLICATE_CODE)
        now = self._now()
        department = Department(
            facility_id=facility.id, **payload.model_dump(), is_active=True, created_at=now, updated_at=now
        )
        self._departments.add(department)
        self._commit(_DUPLICATE_CODE)
        return department

    def update(self, department_id: uuid.UUID, payload: DepartmentUpdate) -> Department:
        department = self.get(department_id)
        changes = payload.model_dump(exclude_unset=True)
        reactivating = changes.get("is_active") is True and not department.is_active
        if reactivating and not self._facilities.get(department.facility_id).is_active:
            raise ConflictError("Departments of an inactive facility cannot be activated")
        changed = False
        for field, value in changes.items():
            if getattr(department, field) != value:
                setattr(department, field, value)
                changed = True
        if changed:
            department.updated_at = self._now()
            self._commit("Department update conflicts with existing data")
        return department
