import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.slots import SlotSource


class SlotRead(BaseModel):
    start_utc: datetime
    end_utc: datetime
    start_local: datetime = Field(description="Slot start in the facility timezone (ISO 8601 with offset)")
    end_local: datetime = Field(description="Slot end in the facility timezone (ISO 8601 with offset)")
    source: SlotSource


class SlotsResponse(BaseModel):
    provider_id: uuid.UUID
    facility_id: uuid.UUID
    timezone: str = Field(description="Facility IANA timezone used to interpret working hours")
    date_from: date = Field(description="Facility-local date (inclusive)")
    date_to: date = Field(description="Facility-local date (inclusive)")
    advisory: Literal[True] = Field(
        default=True,
        description="Slots are advisory only; the Appointment service owns final booking correctness",
    )
    slots: list[SlotRead]
