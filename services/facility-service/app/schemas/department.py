import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.types import Code, Floor, Name, PhoneExtension


class DepartmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Code = Field(description="Unique within the facility; stored uppercase", examples=["CARDIO"])
    name: Name = Field(examples=["Cardiology"])
    floor: Floor | None = Field(default=None, examples=["3"])
    phone_extension: PhoneExtension | None = Field(default=None, examples=["2101"])


class DepartmentUpdate(BaseModel):
    """Partial update. `code` is immutable. Set `is_active` to deactivate or re-activate."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    floor: Floor | None = None
    phone_extension: PhoneExtension | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _reject_null_for_required(self) -> "DepartmentUpdate":
        for field in ("name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    facility_id: uuid.UUID
    code: str
    name: str
    floor: str | None
    phone_extension: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
