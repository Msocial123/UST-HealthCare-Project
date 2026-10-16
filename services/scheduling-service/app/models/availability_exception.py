import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Index, String, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime


class AvailabilityException(Base):
    """Leave, holiday, block or extra hours for a provider, as a UTC interval.

    facility_id NULL means the exception applies at every facility. Only a structured reason_code is
    stored; there is deliberately no free-text field.
    """

    __tablename__ = "availability_exceptions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        CheckConstraint("type IN ('LEAVE', 'HOLIDAY', 'BLOCKED', 'EXTRA_HOURS')", name="type_allowed"),
        CheckConstraint("type <> 'EXTRA_HOURS' OR facility_id IS NOT NULL", name="extra_hours_facility"),
        CheckConstraint("reason_code = upper(reason_code)", name="reason_code_uppercase"),
        Index("ix_availability_exceptions_provider_id_starts_at", "provider_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    facility_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime)
    type: Mapped[str] = mapped_column(String(16))
    reason_code: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
