import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from app.domain.appointments import AppointmentStatus, interval_problem
from app.schemas.types import ReasonCode, UtcDatetime

_REASON = "Structured administrative code only (e.g. FOLLOW_UP, NEW_PATIENT); never clinical or free text"
_CANCEL_REASON = "Structured code only (e.g. PATIENT_REQUEST, PROVIDER_UNAVAILABLE); never free text"
_VERSION = "Current version from the last read (optimistic lock); a stale value returns 409"


def _check_interval(starts_at: datetime, ends_at: datetime) -> None:
    problem = interval_problem(starts_at, ends_at)
    if problem:
        raise PydanticCustomError("invalid_interval", problem)


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: uuid.UUID
    provider_id: uuid.UUID
    facility_id: uuid.UUID
    starts_at: UtcDatetime = Field(description="Timezone-aware; stored as UTC")
    ends_at: UtcDatetime = Field(description="Timezone-aware; stored as UTC (exclusive)")
    reason_code: ReasonCode = Field(description=_REASON, examples=["FOLLOW_UP"])

    @model_validator(mode="after")
    def _check(self) -> "AppointmentCreate":
        _check_interval(self.starts_at, self.ends_at)
        return self


class AppointmentReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: UtcDatetime = Field(description="Timezone-aware; stored as UTC")
    ends_at: UtcDatetime = Field(description="Timezone-aware; stored as UTC (exclusive)")
    version: int = Field(ge=1, description=_VERSION)

    @model_validator(mode="after")
    def _check(self) -> "AppointmentReschedule":
        _check_interval(self.starts_at, self.ends_at)
        return self


class AppointmentCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cancellation_reason: ReasonCode = Field(description=_CANCEL_REASON, examples=["PATIENT_REQUEST"])
    version: int | None = Field(default=None, ge=1, description=_VERSION + " (optional)")


class StatusTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1, description=_VERSION + " (optional)")


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    provider_id: uuid.UUID
    facility_id: uuid.UUID
    starts_at: datetime = Field(description="UTC")
    ends_at: datetime = Field(description="UTC (exclusive)")
    status: AppointmentStatus
    reason_code: str
    cancellation_reason: str | None
    version: int
    created_by: uuid.UUID
    created_at: datetime = Field(description="UTC")
    updated_at: datetime = Field(description="UTC")
