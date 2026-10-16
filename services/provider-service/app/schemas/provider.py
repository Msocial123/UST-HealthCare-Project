import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.models.provider import Provider

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
WorkPhone = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=7, max_length=32, pattern=r"^\+?[0-9][0-9 ()-]{5,30}$"
    ),
]
LicenseNumber = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=4, max_length=32, pattern=r"^[A-Za-z0-9-]+$"),
    AfterValidator(str.upper),
]
YearsOfExperience = Annotated[int, Field(ge=0, le=70)]


class SpecialtyAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specialty_id: uuid.UUID
    is_primary: bool = False


SpecialtyAssignments = Annotated[list[SpecialtyAssignment], Field(min_length=1, max_length=20)]


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title = Field(examples=["Dr"])
    first_name: PersonName
    last_name: PersonName
    work_email: EmailStr
    work_phone: WorkPhone
    license_number: LicenseNumber = Field(description="Synthetic license identifier; stored uppercase")
    years_of_experience: YearsOfExperience
    facility_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    specialties: SpecialtyAssignments = Field(
        description="One or more specialties; exactly one must be primary"
    )


class ProviderUpdate(BaseModel):
    """Partial update. When `specialties` is provided it replaces the full assignment set."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    first_name: PersonName | None = None
    last_name: PersonName | None = None
    work_email: EmailStr | None = None
    work_phone: WorkPhone | None = None
    license_number: LicenseNumber | None = None
    years_of_experience: YearsOfExperience | None = None
    facility_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    specialties: SpecialtyAssignments | None = None

    @model_validator(mode="after")
    def _reject_null_for_required(self) -> "ProviderUpdate":
        nullable = {"facility_id", "department_id"}
        for field in self.model_fields_set - nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ProviderSpecialtyRead(BaseModel):
    specialty_id: uuid.UUID
    code: str
    name: str
    is_primary: bool
    is_active: bool


class ProviderRead(BaseModel):
    id: uuid.UUID
    provider_number: str
    title: str
    first_name: str
    last_name: str
    work_email: str
    work_phone: str
    license_number: str
    years_of_experience: int
    is_active: bool
    facility_id: uuid.UUID | None
    department_id: uuid.UUID | None
    specialties: list[ProviderSpecialtyRead]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, provider: "Provider") -> "ProviderRead":
        return cls(
            id=provider.id,
            provider_number=provider.provider_number,
            title=provider.title,
            first_name=provider.first_name,
            last_name=provider.last_name,
            work_email=provider.work_email,
            work_phone=provider.work_phone,
            license_number=provider.license_number,
            years_of_experience=provider.years_of_experience,
            is_active=provider.is_active,
            facility_id=provider.facility_id,
            department_id=provider.department_id,
            specialties=[
                ProviderSpecialtyRead(
                    specialty_id=link.specialty_id,
                    code=link.specialty.code,
                    name=link.specialty.name,
                    is_primary=link.is_primary,
                    is_active=link.specialty.is_active,
                )
                for link in sorted(
                    provider.specialty_links, key=lambda item: (not item.is_primary, item.specialty.code)
                )
            ],
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )
