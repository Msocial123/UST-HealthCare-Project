import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.facilities import RoomType
from app.schemas.types import RoomNumber


class RoomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_number: RoomNumber = Field(
        description="Unique within the department; stored uppercase", examples=["3A-12"]
    )
    room_type: RoomType


class RoomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    department_id: uuid.UUID
    room_number: str
    room_type: RoomType
    is_active: bool
    created_at: datetime
    updated_at: datetime
