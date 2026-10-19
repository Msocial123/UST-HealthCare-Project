"""Appointment lifecycle rules (pure functions, no I/O)."""

from collections.abc import Iterable
from datetime import datetime, timedelta
from enum import StrEnum

REASON_CODE_PATTERN = r"^[A-Za-z0-9_]+$"
MIN_DURATION = timedelta(minutes=5)
MAX_DURATION = timedelta(hours=8)


class AppointmentStatus(StrEnum):
    BOOKED = "BOOKED"
    CHECKED_IN = "CHECKED_IN"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


# Statuses that occupy the provider's time. CANCELLED and NO_SHOW release it.
SLOT_OCCUPYING_STATUSES: tuple[AppointmentStatus, ...] = (
    AppointmentStatus.BOOKED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.COMPLETED,
)

ALLOWED_TRANSITIONS: dict[AppointmentStatus, frozenset[AppointmentStatus]] = {
    AppointmentStatus.BOOKED: frozenset(
        {AppointmentStatus.CHECKED_IN, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}
    ),
    AppointmentStatus.CHECKED_IN: frozenset({AppointmentStatus.COMPLETED}),
}


class EventType(StrEnum):
    APPOINTMENT_CREATED = "AppointmentCreated"
    APPOINTMENT_RESCHEDULED = "AppointmentRescheduled"
    APPOINTMENT_CANCELLED = "AppointmentCancelled"


def can_transition(current: AppointmentStatus, target: AppointmentStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def interval_problem(starts_at: datetime, ends_at: datetime) -> str | None:
    """Static interval rules; messages never contain the submitted values."""
    if ends_at <= starts_at:
        return "ends_at must be after starts_at"
    duration = ends_at - starts_at
    if duration < MIN_DURATION:
        return "Appointment must last at least 5 minutes"
    if duration > MAX_DURATION:
        return "Appointment must not last longer than 8 hours"
    return None


def interval_covered(
    windows: Iterable[tuple[datetime, datetime]], starts_at: datetime, ends_at: datetime
) -> bool:
    """True when the union of half-open windows covers [starts_at, ends_at) without gaps."""
    cursor = starts_at
    for window_start, window_end in sorted(windows):
        if window_start > cursor:
            break
        if window_end > cursor:
            cursor = window_end
        if cursor >= ends_at:
            return True
    return cursor >= ends_at
