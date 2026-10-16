import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, CheckConstraint, Date, Index, SmallInteger, Time, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime


class WorkingHours(Base):
    """Weekly working-hours rule in facility-local wall-clock time.

    provider_id and facility_id are opaque references to other services; there are no foreign keys.
    """

    __tablename__ = "working_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint("slot_minutes BETWEEN 5 AND 120", name="slot_minutes_range"),
        CheckConstraint("end_local_time > start_local_time", name="end_after_start"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="valid_range"),
        Index("ix_working_hours_provider_id_weekday", "provider_id", "weekday"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    facility_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_local_time: Mapped[time] = mapped_column(Time)
    end_local_time: Mapped[time] = mapped_column(Time)
    slot_minutes: Mapped[int] = mapped_column(SmallInteger)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
