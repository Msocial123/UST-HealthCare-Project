"""Room use cases."""

import uuid

from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models.room import Room
from app.repositories.room_repository import RoomRepository
from app.schemas.room import RoomCreate
from app.services._base import BaseService, Clock
from app.services.department_service import DepartmentService
from app.services.facility_service import FacilityService

_DUPLICATE_NUMBER = "A room with this number already exists in this department"


class RoomService(BaseService):
    def __init__(self, session: Session, clock: Clock) -> None:
        super().__init__(session, clock)
        self._rooms = RoomRepository(session)
        self._departments = DepartmentService(session, clock)
        self._facilities = FacilityService(session, clock)

    def list_for_department(
        self, department_id: uuid.UUID, *, active: bool | None, limit: int, offset: int
    ) -> tuple[list[Room], int]:
        self._departments.get(department_id)
        return self._rooms.list_for_department(department_id, active=active, limit=limit, offset=offset)

    def create(self, department_id: uuid.UUID, payload: RoomCreate) -> Room:
        department = self._departments.get(department_id)
        if not department.is_active:
            raise ConflictError("Rooms cannot be created in an inactive department")
        if not self._facilities.get(department.facility_id).is_active:
            raise ConflictError("Rooms cannot be created in an inactive facility")
        if self._rooms.room_number_exists(department.id, payload.room_number):
            raise ConflictError(_DUPLICATE_NUMBER)
        now = self._now()
        room = Room(
            department_id=department.id,
            **payload.model_dump(mode="json"),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._rooms.add(room)
        self._commit(_DUPLICATE_NUMBER)
        return room
