import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Index, String, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (
        CheckConstraint("code = upper(code)", name="code_uppercase"),
        CheckConstraint(
            "facility_type IN ('HOSPITAL', 'CLINIC', 'DIAGNOSTIC_CENTER')", name="facility_type_allowed"
        ),
        CheckConstraint("country_code = upper(country_code)", name="country_code_uppercase"),
        Index("ix_facilities_name", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    facility_type: Mapped[str] = mapped_column(String(32))
    address_line1: Mapped[str] = mapped_column(String(200))
    address_line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    state_province: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str] = mapped_column(String(16))
    country_code: Mapped[str] = mapped_column(String(2))
    main_phone: Mapped[str] = mapped_column(String(32))
    # IANA timezone name (e.g. Asia/Kolkata). Timestamps are stored in UTC; this is for local-time conversion.
    timezone: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
