import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.specialty import Specialty


class SpecialtyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, specialty_id: uuid.UUID) -> Specialty | None:
        return self._session.get(Specialty, specialty_id)

    def get_many(self, specialty_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Specialty]:
        ids = list(specialty_ids)
        if not ids:
            return {}
        rows = self._session.scalars(select(Specialty).where(Specialty.id.in_(ids)))
        return {row.id: row for row in rows}

    def code_exists(self, code: str) -> bool:
        return self._session.scalar(select(Specialty.id).where(Specialty.code == code)) is not None

    def name_exists(self, name: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(Specialty.id).where(func.lower(Specialty.name) == name.lower())
        if exclude_id is not None:
            stmt = stmt.where(Specialty.id != exclude_id)
        return self._session.scalar(stmt) is not None

    def list(self, *, active: bool | None, limit: int, offset: int) -> tuple[list[Specialty], int]:
        stmt = select(Specialty)
        if active is not None:
            stmt = stmt.where(Specialty.is_active.is_(active))
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self._session.scalars(stmt.order_by(Specialty.code).limit(limit).offset(offset)).all()
        return list(items), total

    def add(self, specialty: Specialty) -> Specialty:
        self._session.add(specialty)
        return specialty
