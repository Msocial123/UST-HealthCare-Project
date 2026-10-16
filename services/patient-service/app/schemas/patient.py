import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, StringConstraints, model_validator

from app.core.time import utcnow
from app.domain.patients import Sex

EARLIEST_DATE_OF_BIRTH = date(1900, 1, 1)

PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Phone = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=7, max_length=32, pattern=r"^\+?[0-9][0-9 ()\-]*$"),
]
NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]
AddressLine = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Locality = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
PostalCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9 \-]+$")
]
CountryCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z]{2}$")
]  # ISO 3166-1 alpha-2


def _validate_date_of_birth(value: date) -> date:
    if value < EARLIEST_DATE_OF_BIRTH:
        raise ValueError("date_of_birth is too far in the past")
    if value > utcnow().date():
        raise ValueError("date_of_birth must not be in the future")
    return value


DateOfBirth = Annotated[date, AfterValidator(_validate_date_of_birth)]

REQUIRED_DEMOGRAPHICS = frozenset({"first_name", "last_name", "date_of_birth", "sex"})


class _ContactAndAddress(BaseModel):
    phone: Phone | None = None
    email: NormalizedEmail | None = None
    address_line1: AddressLine | None = None
    address_line2: AddressLine | None = None
    city: Locality | None = None
    state: Locality | None = None
    postal_code: PostalCode | None = None
    country: CountryCode | None = None


class PatientCreate(_ContactAndAddress):
    model_config = ConfigDict(extra="forbid")

    first_name: PersonName
    last_name: PersonName
    date_of_birth: DateOfBirth
    sex: Sex


class PatientUpdate(_ContactAndAddress):
    """Partial demographics update. MRN, id and active status cannot be changed here."""

    model_config = ConfigDict(extra="forbid")

    first_name: PersonName | None = None
    last_name: PersonName | None = None
    date_of_birth: DateOfBirth | None = None
    sex: Sex | None = None

    @model_validator(mode="after")
    def _check_fields(self) -> "PatientUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        for name in self.model_fields_set & REQUIRED_DEMOGRAPHICS:
            if getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        return self


class PatientSummary(BaseModel):
    """Minimal fields returned by list/search."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    medical_record_number: str
    first_name: str
    last_name: str
    date_of_birth: date
    sex: Sex
    is_active: bool


class PatientRead(PatientSummary):
    phone: str | None
    email: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    created_at: datetime
    updated_at: datetime
