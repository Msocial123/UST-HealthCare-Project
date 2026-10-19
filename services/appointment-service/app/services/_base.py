from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

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
