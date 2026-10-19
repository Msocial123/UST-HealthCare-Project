import uuid
from datetime import datetime

from sqlalchemy import DDL, CheckConstraint, Index, Integer, String, Uuid, event, func, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime
from app.domain.appointments import SLOT_OCCUPYING_STATUSES, AppointmentStatus

STATUS_ALLOWED_SQL = "status IN ({})".format(", ".join(f"'{s.value}'" for s in AppointmentStatus))
SLOT_OCCUPYING_SQL = "status IN ({})".format(", ".join(f"'{s.value}'" for s in SLOT_OCCUPYING_STATUSES))
PROVIDER_OVERLAP_CONSTRAINT = "ex_appointments_provider_overlap"


class Appointment(Base):
    """A booked provider time slot for a patient.

    patient_id, provider_id and facility_id are opaque references to other services; no foreign keys.
    On PostgreSQL the exclusion constraint is the final authority against double-booking: two
    slot-occupying appointments of the same provider can never have overlapping [starts_at, ends_at).
    """

    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        CheckConstraint(STATUS_ALLOWED_SQL, name="status_allowed"),
        CheckConstraint(
            "(status = 'CANCELLED') = (cancellation_reason IS NOT NULL)",
            name="cancellation_reason_iff_cancelled",
        ),
        CheckConstraint("reason_code = upper(reason_code)", name="reason_code_uppercase"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_appointments_provider_id_starts_at", "provider_id", "starts_at"),
        Index("ix_appointments_patient_id_starts_at", "patient_id", "starts_at"),
        Index("ix_appointments_status", "status"),
        ExcludeConstraint(
            ("provider_id", "="),
            (text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            name=PROVIDER_OVERLAP_CONSTRAINT,
            using="gist",
            where=text(SLOT_OCCUPYING_SQL),
        ).ddl_if(dialect="postgresql"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    provider_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    facility_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(16))
    reason_code: Mapped[str] = mapped_column(String(32))
    cancellation_reason: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())

    # Optimistic lock: every UPDATE is "... WHERE version = <loaded>" and increments it.
    __mapper_args__ = {"version_id_col": version}


# The exclusion constraint compares a UUID with "=" inside a GiST index, which needs btree_gist.
# Alembic creates the extension in the migration; this covers metadata.create_all() in tests.
event.listen(
    Appointment.__table__,
    "before_create",
    DDL("CREATE EXTENSION IF NOT EXISTS btree_gist").execute_if(dialect="postgresql"),
)
