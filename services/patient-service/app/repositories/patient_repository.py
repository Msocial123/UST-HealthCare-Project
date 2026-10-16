import re
import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.patient import Patient

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LIKE_ESCAPE = "\\"


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parse_iso_date(token: str) -> date | None:
    if not _ISO_DATE.match(token):
        return None
    try:
        return date.fromisoformat(token)
    except ValueError:
        return None


def _token_condition(token: str) -> ColumnElement[bool]:
    """One search term matches a name prefix (case-insensitive), an exact MRN or an exact date of birth."""
    prefix = _escape_like(token.lower()) + "%"
    options: list[ColumnElement[bool]] = [
        func.lower(Patient.first_name).like(prefix, escape=_LIKE_ESCAPE),
        func.lower(Patient.last_name).like(prefix, escape=_LIKE_ESCAPE),
        Patient.medical_record_number == token.upper(),
    ]
    parsed = _parse_iso_date(token)
    if parsed is not None:
        options.append(Patient.date_of_birth == parsed)
    return or_(*options)


class PatientRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, patient_id: uuid.UUID, *, for_update: bool = False) -> Patient | None:
        if not for_update:
            return self._session.get(Patient, patient_id)
        statement = (
            select(Patient)
            .where(Patient.id == patient_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(statement)

    def search(
        self, *, terms: Sequence[str], limit: int, offset: int, is_active: bool | None = None
    ) -> tuple[Sequence[Patient], int]:
        filters: list[ColumnElement[bool]] = []
        if terms:
            filters.append(and_(*(_token_condition(term) for term in terms)))
        if is_active is not None:
            filters.append(Patient.is_active.is_(is_active))
        total = self._session.scalar(select(func.count()).select_from(Patient).where(*filters)) or 0
        items = self._session.scalars(
            select(Patient)
            .where(*filters)
            .order_by(
                func.lower(Patient.last_name), func.lower(Patient.first_name), Patient.created_at, Patient.id
            )
            .limit(limit)
            .offset(offset)
        ).all()
        return items, total

    def add(self, patient: Patient) -> Patient:
        self._session.add(patient)
        self._session.flush()
        return patient
