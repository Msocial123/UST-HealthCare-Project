import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    false,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime
from app.models.specialty import Specialty


class Provider(Base):
    __tablename__ = "providers"
    __table_args__ = (
        CheckConstraint(
            "years_of_experience >= 0 AND years_of_experience <= 70", name="years_of_experience_range"
        ),
        Index("ix_providers_last_name_first_name", "last_name", "first_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider_number: Mapped[str] = mapped_column(String(16), unique=True)
    title: Mapped[str] = mapped_column(String(20))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    work_email: Mapped[str] = mapped_column(String(254))
    work_phone: Mapped[str] = mapped_column(String(32))
    license_number: Mapped[str] = mapped_column(String(32), unique=True)
    years_of_experience: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Plain references owned by the (future) Facility service; never validated or joined here.
    facility_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())

    specialty_links: Mapped[list["ProviderSpecialty"]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ProviderSpecialty(Base):
    __tablename__ = "provider_specialties"
    __table_args__ = (
        # At most one primary per provider is enforced by the database; "at least one" by the service layer.
        Index(
            "uq_provider_specialties_one_primary",
            "provider_id",
            unique=True,
            postgresql_where=text("is_primary"),
            sqlite_where=text("is_primary"),
        ),
        Index("ix_provider_specialties_specialty_id", "specialty_id"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True
    )
    specialty_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("specialties.id", ondelete="RESTRICT"), primary_key=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())

    provider: Mapped[Provider] = relationship(back_populates="specialty_links")
    specialty: Mapped[Specialty] = relationship(lazy="joined")
