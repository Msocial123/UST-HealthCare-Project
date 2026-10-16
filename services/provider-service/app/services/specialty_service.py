import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.time import utcnow
from app.models.specialty import Specialty
from app.repositories.specialty_repository import SpecialtyRepository
from app.schemas.specialty import SpecialtyCreate, SpecialtyUpdate


class SpecialtyService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = SpecialtyRepository(session)

    def create(self, payload: SpecialtyCreate) -> Specialty:
        if self._repo.code_exists(payload.code):
            raise ConflictError("A specialty with this code already exists")
        if self._repo.name_exists(payload.name):
            raise ConflictError("A specialty with this name already exists")
        specialty = self._repo.add(Specialty(**payload.model_dump()))
        self._commit()
        return specialty

    def list(self, *, active: bool | None, limit: int, offset: int) -> tuple[list[Specialty], int]:
        return self._repo.list(active=active, limit=limit, offset=offset)

    def update(self, specialty_id: uuid.UUID, payload: SpecialtyUpdate) -> Specialty:
        specialty = self._repo.get(specialty_id)
        if specialty is None:
            raise NotFoundError("Specialty not found")
        changes = payload.model_dump(exclude_unset=True)
        if "name" in changes and self._repo.name_exists(changes["name"], exclude_id=specialty.id):
            raise ConflictError("A specialty with this name already exists")
        for field, value in changes.items():
            setattr(specialty, field, value)
        if changes:
            specialty.updated_at = utcnow()
            self._commit()
        return specialty

    def _commit(self) -> None:
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError("Specialty conflicts with an existing record") from None
