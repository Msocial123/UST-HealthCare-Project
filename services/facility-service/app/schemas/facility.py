import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.facilities import FacilityType
from app.schemas.types import AddressLine, Code, CountryCode, Locality, Name, Phone, PostalCode, Timezone


class FacilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Code = Field(description="Unique; stored uppercase, e.g. NHG-MAIN", examples=["NHG-MAIN"])
    name: Name = Field(examples=["Northwind General Hospital"])
    facility_type: FacilityType
    address_line1: AddressLine = Field(examples=["100 Example Avenue"])
    address_line2: AddressLine | None = None
    city: Locality = Field(examples=["Sampleton"])
    state_province: Locality | None = None
    postal_code: PostalCode = Field(examples=["560001"])
    country_code: CountryCode = Field(description="ISO 3166-1 alpha-2, stored uppercase", examples=["IN"])
    main_phone: Phone = Field(examples=["+91 80 5550 0100"])
    timezone: Timezone = Field(description="IANA timezone name", examples=["Asia/Kolkata"])


class FacilityUpdate(BaseModel):
    """Partial update. `code` is immutable; `is_active` changes only via /activate and /deactivate."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    facility_type: FacilityType | None = None
    address_line1: AddressLine | None = None
    address_line2: AddressLine | None = None
    city: Locality | None = None
    state_province: Locality | None = None
    postal_code: PostalCode | None = None
    country_code: CountryCode | None = None
    main_phone: Phone | None = None
    timezone: Timezone | None = None

    @model_validator(mode="after")
    def _reject_null_for_required(self) -> "FacilityUpdate":
        nullable = {"address_line2", "state_province"}
        for field in self.model_fields_set - nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class FacilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    facility_type: FacilityType
    address_line1: str
    address_line2: str | None
    city: str
    state_province: str | None
    postal_code: str
    country_code: str
    main_phone: str
    timezone: str
    is_active: bool
    created_at: datetime = Field(description="UTC")
    updated_at: datetime = Field(description="UTC")


class FacilityDetail(FacilityRead):
    current_local_time: datetime = Field(description="Current wall-clock time in the facility timezone")
    utc_offset: str = Field(description="Current UTC offset of the facility timezone", examples=["+05:30"])
