import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, Index, String, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime
from app.domain.patients import MRN_LENGTH, Sex

SEX_VALUES_SQL = ", ".join(f"'{sex.value}'" for sex in Sex)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    medical_record_number: Mapped[str] = mapped_column(String(MRN_LENGTH), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[str] = mapped_column(String(16), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"sex IN ({SEX_VALUES_SQL})", name="sex_valid"),
        CheckConstraint("email IS NULL OR email = lower(email)", name="email_lowercase"),
        Index("ix_patients_last_name_lower", func.lower(last_name)),
        Index("ix_patients_first_name_lower", func.lower(first_name)),
        Index("ix_patients_date_of_birth", date_of_birth),
    )

    def __repr__(self) -> str:  # never include names, DOB or contact details
        return f"Patient(id={self.id!s}, is_active={self.is_active})"
