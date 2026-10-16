import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.room import Room


class RoomRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def room_number_exists(self, department_id: uuid.UUID, room_number: str) -> bool:
        stmt = select(Room.id).where(Room.department_id == department_id, Room.room_number == room_number)
        return self._session.scalar(stmt) is not None

    def list_for_department(
        self, department_id: uuid.UUID, *, active: bool | None, limit: int, offset: int
    ) -> tuple[list[Room], int]:
        stmt = select(Room).where(Room.department_id == department_id)
        if active is not None:
            stmt = stmt.where(Room.is_active.is_(active))
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        ordered = stmt.order_by(Room.room_number)
        return list(self._session.scalars(ordered.limit(limit).offset(offset)).all()), total

    def add(self, room: Room) -> Room:
        self._session.add(room)
        return room
