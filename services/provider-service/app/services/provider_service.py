"""Provider profile use cases. Business rules live here, not in route handlers."""

import secrets
import uuid
from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.core.time import utcnow
from app.models.provider import Provider, ProviderSpecialty
from app.repositories.provider_repository import ProviderRepository
from app.repositories.specialty_repository import SpecialtyRepository
from app.schemas.provider import ProviderCreate, ProviderUpdate, SpecialtyAssignment

PROVIDER_NUMBER_PREFIX = "PRV-"
_PROVIDER_NUMBER_ATTEMPTS = 5


def generate_provider_number() -> str:
    return PROVIDER_NUMBER_PREFIX + secrets.token_hex(4).upper()


class ProviderService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._providers = ProviderRepository(session)
        self._specialties = SpecialtyRepository(session)

    def get(self, provider_id: uuid.UUID) -> Provider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise NotFoundError("Provider not found")
        return provider

    def search(
        self, *, search: str | None, specialty_code: str | None, active: bool | None, limit: int, offset: int
    ) -> tuple[list[Provider], int]:
        return self._providers.search(
            search=search, specialty_code=specialty_code, active=active, limit=limit, offset=offset
        )

    def create(self, payload: ProviderCreate) -> Provider:
        self._validate_assignments(payload.specialties, currently_assigned=set())
        if self._providers.license_number_exists(payload.license_number):
            raise ConflictError("A provider with this license number already exists")

        provider = Provider(
            provider_number=self._new_provider_number(),
            **payload.model_dump(exclude={"specialties"}),
        )
        provider.specialty_links = [
            ProviderSpecialty(specialty_id=item.specialty_id, is_primary=item.is_primary)
            for item in payload.specialties
        ]
        self._providers.add(provider)
        self._commit()
        return provider

    def update(self, provider_id: uuid.UUID, payload: ProviderUpdate) -> Provider:
        provider = self.get(provider_id)
        changes = payload.model_dump(exclude_unset=True, exclude={"specialties"})
        if "license_number" in changes and self._providers.license_number_exists(
            changes["license_number"], exclude_id=provider.id
        ):
            raise ConflictError("A provider with this license number already exists")
        if payload.specialties is not None:
            current = {link.specialty_id for link in provider.specialty_links}
            self._validate_assignments(payload.specialties, currently_assigned=current)

        for field, value in changes.items():
            setattr(provider, field, value)
        if payload.specialties is not None:
            self._replace_specialties(provider, payload.specialties)
        if changes or payload.specialties is not None:
            provider.updated_at = utcnow()
            self._commit()
        return provider

    def set_active(self, provider_id: uuid.UUID, *, active: bool) -> Provider:
        provider = self.get(provider_id)
        if provider.is_active != active:
            provider.is_active = active
            provider.updated_at = utcnow()
            self._commit()
        return provider

    def _validate_assignments(
        self, assignments: Sequence[SpecialtyAssignment], *, currently_assigned: set[uuid.UUID]
    ) -> None:
        ids = [item.specialty_id for item in assignments]
        if len(set(ids)) != len(ids):
            raise DomainValidationError("Each specialty may be assigned only once")
        if sum(1 for item in assignments if item.is_primary) != 1:
            raise DomainValidationError("Exactly one specialty must be marked as primary")

        found = self._specialties.get_many(ids)
        missing = [str(specialty_id) for specialty_id in ids if specialty_id not in found]
        if missing:
            raise NotFoundError("Specialty not found", details={"specialty_ids": missing})
        # Inactive specialties cannot be newly assigned (409). Existing assignments are kept as-is.
        inactive = [
            str(specialty_id)
            for specialty_id in ids
            if not found[specialty_id].is_active and specialty_id not in currently_assigned
        ]
        if inactive:
            raise ConflictError(
                "Inactive specialties cannot be assigned", details={"specialty_ids": inactive}
            )

    def _replace_specialties(self, provider: Provider, assignments: Sequence[SpecialtyAssignment]) -> None:
        wanted = {item.specialty_id: item.is_primary for item in assignments}
        # Clear the primary flag first so the one-primary unique index never sees two primaries mid-flush.
        for link in list(provider.specialty_links):
            link.is_primary = False
            if link.specialty_id not in wanted:
                provider.specialty_links.remove(link)
        self._session.flush()

        existing = {link.specialty_id: link for link in provider.specialty_links}
        for specialty_id, is_primary in wanted.items():
            link = existing.get(specialty_id)
            if link is None:
                provider.specialty_links.append(
                    ProviderSpecialty(specialty_id=specialty_id, is_primary=is_primary)
                )
            else:
                link.is_primary = is_primary
        self._session.flush()
        self._session.expire(provider, ["specialty_links"])

    def _new_provider_number(self) -> str:
        for _ in range(_PROVIDER_NUMBER_ATTEMPTS):
            candidate = generate_provider_number()
            if not self._providers.provider_number_exists(candidate):
                return candidate
        raise ConflictError("Could not allocate a unique provider number; retry the request")

    def _commit(self) -> None:
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError("Provider conflicts with an existing record") from None
