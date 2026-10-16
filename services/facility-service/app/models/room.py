import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint("room_number = upper(room_number)", name="room_number_uppercase"),
        CheckConstraint(
            "room_type IN ('CONSULTATION', 'WARD', 'PROCEDURE', 'OTHER')", name="room_type_allowed"
        ),
        UniqueConstraint("department_id", "room_number", name="uq_rooms_department_id_room_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"))
    room_number: Mapped[str] = mapped_column(String(16))
    room_type: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
