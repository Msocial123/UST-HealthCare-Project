import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from app.domain.scheduling import MAX_SLOT_MINUTES, MIN_SLOT_MINUTES, working_hours_problem

_WEEKDAY = "ISO weekday index: 0 = Monday ... 6 = Sunday"


class WorkingHoursCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facility_id: uuid.UUID = Field(description="Facility (Facility service ID) the hours apply to")
    weekday: int = Field(ge=0, le=6, description=_WEEKDAY, examples=[0])
    start_local_time: time = Field(description="Facility-local wall-clock time (HH:MM)", examples=["09:00"])
    end_local_time: time = Field(description="Facility-local wall-clock time (HH:MM)", examples=["17:00"])
    slot_minutes: int = Field(ge=MIN_SLOT_MINUTES, le=MAX_SLOT_MINUTES, examples=[30])
    valid_from: date = Field(description="First facility-local date the rule applies (inclusive)")
    valid_to: date | None = Field(
        default=None, description="Last facility-local date (inclusive); open-ended"
    )

    @model_validator(mode="after")
    def _check_rule(self) -> "WorkingHoursCreate":
        problem = working_hours_problem(
            self.start_local_time, self.end_local_time, self.slot_minutes, self.valid_from, self.valid_to
        )
        if problem:
            raise PydanticCustomError("invalid_rule", problem)
        return self


class WorkingHoursUpdate(BaseModel):
    """Partial update. provider_id and facility_id are immutable; is_active=true re-activates a rule."""

    model_config = ConfigDict(extra="forbid")

    weekday: int | None = Field(default=None, ge=0, le=6, description=_WEEKDAY)
    start_local_time: time | None = None
    end_local_time: time | None = None
    slot_minutes: int | None = Field(default=None, ge=MIN_SLOT_MINUTES, le=MAX_SLOT_MINUTES)
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _reject_null_for_required(self) -> "WorkingHoursUpdate":
        for field in self.model_fields_set - {"valid_to"}:
            if getattr(self, field) is None:
                raise PydanticCustomError("invalid_rule", f"{field} cannot be null")
        return self


class WorkingHoursRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    facility_id: uuid.UUID
    weekday: int
    start_local_time: time
    end_local_time: time
    slot_minutes: int
    valid_from: date
    valid_to: date | None
    is_active: bool
    created_at: datetime = Field(description="UTC")
    updated_at: datetime = Field(description="UTC")
