import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, String, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime
from app.domain.roles import Role

ROLE_VALUES_SQL = ", ".join(f"'{role.value}'" for role in Role)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN ({ROLE_VALUES_SQL})", name="role_valid"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    def __repr__(self) -> str:  # never include password_hash
        return f"User(id={self.id!s}, role={self.role}, is_active={self.is_active})"
