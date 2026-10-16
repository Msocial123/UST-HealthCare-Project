import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

SpecialtyCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_]+$"),
    AfterValidator(str.upper),
]
SpecialtyName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class SpecialtyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: SpecialtyCode = Field(description="Stored uppercase, e.g. CARDIOLOGY")
    name: SpecialtyName
    description: Description | None = None
    is_active: bool = True


class SpecialtyUpdate(BaseModel):
    """Partial update. `code` is immutable because it is used as a stable search key."""

    model_config = ConfigDict(extra="forbid")

    name: SpecialtyName | None = None
    description: Description | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _reject_null_for_required(self) -> "SpecialtyUpdate":
        for field in ("name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class SpecialtyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
