import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.tokens import Principal
from app.domain import patients as patient_domain
from app.models.patient import Patient
from app.repositories.patient_repository import PatientRepository
from app.schemas.common import Page
from app.schemas.patient import PatientCreate, PatientSummary, PatientUpdate

logger = logging.getLogger(__name__)

MRN_ALLOCATION_ATTEMPTS = 5
MAX_SEARCH_TERMS = 5


def _search_terms(search: str | None) -> list[str]:
    return search.split()[:MAX_SEARCH_TERMS] if search else []


class PatientService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._patients = PatientRepository(session)

    def search_patients(
        self, *, search: str | None, limit: int, offset: int, is_active: bool | None = None
    ) -> Page[PatientSummary]:
        items, total = self._patients.search(
            terms=_search_terms(search), limit=limit, offset=offset, is_active=is_active
        )
        return Page[PatientSummary](
            items=[PatientSummary.model_validate(patient) for patient in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_patient(self, patient_id: uuid.UUID) -> Patient:
        patient = self._patients.get_by_id(patient_id)
        if patient is None:
            raise NotFoundError("Patient not found")
        return patient

    def register_patient(self, data: PatientCreate, *, actor: Principal) -> Patient:
        values = data.model_dump()
        values["sex"] = data.sex.value
        for _ in range(MRN_ALLOCATION_ATTEMPTS):
            patient = Patient(medical_record_number=patient_domain.generate_mrn(), **values)
            try:
                self._patients.add(patient)
                self._session.commit()
            except IntegrityError:
                # The only unique constraint is the MRN, so a collision is retried with a fresh MRN.
                self._session.rollback()
                logger.warning("mrn_collision", extra={"event": "mrn_collision"})
                continue
            logger.info(
                "patient_registered",
                extra={
                    "event": "patient_registered",
                    "patient_id": str(patient.id),
                    "actor_id": str(actor.subject),
                },
            )
            return patient
        raise ConflictError("Could not allocate a unique medical record number; retry the request")

    def update_patient(self, patient_id: uuid.UUID, data: PatientUpdate, *, actor: Principal) -> Patient:
        patient = self._get_active_for_update(patient_id, "Inactive patients cannot be updated")
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(patient, field, value.value if field == "sex" else value)
        self._session.commit()
        logger.info(
            "patient_updated",
            extra={
                "event": "patient_updated",
                "patient_id": str(patient.id),
                "fields": sorted(changes),
                "actor_id": str(actor.subject),
            },
        )
        return patient

    def deactivate_patient(self, patient_id: uuid.UUID, *, actor: Principal) -> Patient:
        patient = self._get_active_for_update(patient_id, "Patient is already inactive")
        patient.is_active = False
        self._session.commit()
        logger.info(
            "patient_deactivated",
            extra={
                "event": "patient_deactivated",
                "patient_id": str(patient.id),
                "actor_id": str(actor.subject),
            },
        )
        return patient

    def _get_active_for_update(self, patient_id: uuid.UUID, inactive_message: str) -> Patient:
        patient = self._patients.get_by_id(patient_id, for_update=True)
        if patient is None:
            self._session.rollback()
            raise NotFoundError("Patient not found")
        if not patient.is_active:
            self._session.rollback()
            raise ConflictError(inactive_message)
        return patient
