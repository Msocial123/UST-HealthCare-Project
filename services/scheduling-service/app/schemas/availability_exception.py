import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from app.domain.scheduling import ExceptionType, exception_problem
from app.schemas.types import ReasonCode, UtcDatetime

_REASON = "Structured reason code only (e.g. ANNUAL_LEAVE, PUBLIC_HOLIDAY); never free-text details"


class ExceptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facility_id: uuid.UUID | None = Field(
        default=None, description="Facility the exception applies to; null = all facilities"
    )
    starts_at: UtcDatetime = Field(description="Timezone-aware; stored as UTC")
    ends_at: UtcDatetime = Field(description="Timezone-aware; stored as UTC (exclusive)")
    type: ExceptionType
    reason_code: ReasonCode = Field(description=_REASON, examples=["ANNUAL_LEAVE"])

    @model_validator(mode="after")
    def _check_exception(self) -> "ExceptionCreate":
        problem = exception_problem(self.starts_at, self.ends_at, self.type, self.facility_id is not None)
        if problem:
            raise PydanticCustomError("invalid_exception", problem)
        return self


class ExceptionUpdate(BaseModel):
    """Partial update. provider_id and facility_id are immutable; is_active=true re-activates."""

    model_config = ConfigDict(extra="forbid")

    starts_at: UtcDatetime | None = None
    ends_at: UtcDatetime | None = None
    type: ExceptionType | None = None
    reason_code: ReasonCode | None = Field(default=None, description=_REASON)
    is_active: bool | None = None

    @model_validator(mode="after")
    def _reject_null(self) -> "ExceptionUpdate":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise PydanticCustomError("invalid_exception", f"{field} cannot be null")
        return self


class ExceptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    facility_id: uuid.UUID | None
    starts_at: datetime = Field(description="UTC")
    ends_at: datetime = Field(description="UTC (exclusive)")
    type: ExceptionType
    reason_code: str
    is_active: bool
    created_at: datetime = Field(description="UTC")
    updated_at: datetime = Field(description="UTC")
