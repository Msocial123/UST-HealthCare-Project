import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime


class OutboxEvent(Base):
    """Transactional outbox: domain events written in the same transaction as the appointment change.

    A future relay publishes unpublished rows (published_at IS NULL) to the Notification service.
    Payloads contain IDs, times and status only: no reason codes, contact details or clinical data.
    """

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_published_at_occurred_at", "published_at", "occurred_at"),
        Index("ix_outbox_events_aggregate_id", "aggregate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    aggregate_type: Mapped[str] = mapped_column(String(32))
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
