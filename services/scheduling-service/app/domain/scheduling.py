"""Scheduling rules shared by request schemas and services. No clinical logic lives here."""

from datetime import date, datetime, time, timedelta
from enum import StrEnum

MIN_SLOT_MINUTES = 5
MAX_SLOT_MINUTES = 120
MAX_SLOT_RANGE_DAYS = 14
MAX_EXCEPTION_RANGE_DAYS = 366
REASON_CODE_PATTERN = r"^[A-Za-z0-9_]+$"


class ExceptionType(StrEnum):
    LEAVE = "LEAVE"
    HOLIDAY = "HOLIDAY"
    BLOCKED = "BLOCKED"
    EXTRA_HOURS = "EXTRA_HOURS"


BLOCKING_EXCEPTION_TYPES = frozenset({ExceptionType.LEAVE, ExceptionType.HOLIDAY, ExceptionType.BLOCKED})


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def working_hours_problem(
    start: time, end: time, slot_minutes: int, valid_from: date, valid_to: date | None
) -> str | None:
    """Return a safe, value-free description of the first rule violation, or None if the rule is valid."""
    for label, value in (("start_local_time", start), ("end_local_time", end)):
        if value.tzinfo is not None:
            return f"{label} must be a facility-local wall-clock time without a UTC offset"
        if value.second or value.microsecond:
            return f"{label} must be a whole minute (HH:MM)"
    if end <= start:
        return "end_local_time must be after start_local_time"
    if not MIN_SLOT_MINUTES <= slot_minutes <= MAX_SLOT_MINUTES:
        return f"slot_minutes must be between {MIN_SLOT_MINUTES} and {MAX_SLOT_MINUTES}"
    if _minutes(end) - _minutes(start) < slot_minutes:
        return "the working-hours window must be at least one slot long"
    if valid_to is not None and valid_to < valid_from:
        return "valid_to must be on or after valid_from"
    return None


def exception_problem(
    starts_at: datetime, ends_at: datetime, exception_type: ExceptionType, has_facility: bool
) -> str | None:
    """Return a safe, value-free description of the first exception violation, or None if valid."""
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        return "starts_at and ends_at must include a timezone offset"
    if ends_at <= starts_at:
        return "ends_at must be after starts_at"
    if ends_at - starts_at > timedelta(days=MAX_EXCEPTION_RANGE_DAYS):
        return f"an exception may span at most {MAX_EXCEPTION_RANGE_DAYS} days"
    if exception_type == ExceptionType.EXTRA_HOURS and not has_facility:
        return "EXTRA_HOURS exceptions require a facility_id"
    return None


def date_ranges_overlap(
    first_from: date, first_to: date | None, second_from: date, second_to: date | None
) -> bool:
    """Inclusive date ranges; None means open-ended."""
    return (first_to is None or second_from <= first_to) and (second_to is None or first_from <= second_to)
