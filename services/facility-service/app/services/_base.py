from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError

Clock = Callable[[], datetime]


class BaseService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    def _now(self) -> datetime:
        """Current instant from the injected clock, always normalized to timezone-aware UTC."""
        moment = self._clock()
        if moment.tzinfo is None:
            raise ValueError("clock returned a naive datetime")
        return moment.astimezone(UTC)

    def _commit(self, conflict_message: str) -> None:
        """Commit; a unique/foreign-key race that slipped past the pre-checks becomes a 409."""
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(conflict_message) from None
