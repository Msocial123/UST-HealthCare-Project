import uuid

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.models.provider import Provider, ProviderSpecialty
from app.models.specialty import Specialty


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _has_specialty_code(code: str):
    return exists().where(
        ProviderSpecialty.provider_id == Provider.id,
        ProviderSpecialty.specialty_id == Specialty.id,
        Specialty.code == code,
    )


class ProviderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, provider_id: uuid.UUID) -> Provider | None:
        return self._session.get(Provider, provider_id)

    def license_number_exists(self, license_number: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(Provider.id).where(Provider.license_number == license_number)
        if exclude_id is not None:
            stmt = stmt.where(Provider.id != exclude_id)
        return self._session.scalar(stmt) is not None

    def provider_number_exists(self, provider_number: str) -> bool:
        return (
            self._session.scalar(select(Provider.id).where(Provider.provider_number == provider_number))
            is not None
        )

    def search(
        self,
        *,
        search: str | None,
        specialty_code: str | None,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Provider], int]:
        stmt = select(Provider)
        if search:
            pattern = f"%{_escape_like(search.lower())}%"
            full_name = func.lower(Provider.first_name + " " + Provider.last_name)
            stmt = stmt.where(
                or_(
                    full_name.like(pattern, escape="\\"),
                    func.lower(Provider.last_name + " " + Provider.first_name).like(pattern, escape="\\"),
                    func.lower(Provider.provider_number).like(pattern, escape="\\"),
                    _has_specialty_code(search.upper()),
                )
            )
        if specialty_code:
            stmt = stmt.where(_has_specialty_code(specialty_code))
        if active is not None:
            stmt = stmt.where(Provider.is_active.is_(active))
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        ordered = stmt.order_by(Provider.last_name, Provider.first_name, Provider.id)
        items = self._session.scalars(ordered.limit(limit).offset(offset)).all()
        return list(items), total

    def add(self, provider: Provider) -> Provider:
        self._session.add(provider)
        return provider
