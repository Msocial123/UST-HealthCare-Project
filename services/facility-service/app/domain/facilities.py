"""Facility-domain enumerations and timezone helpers."""

from datetime import datetime
from enum import StrEnum
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones


class FacilityType(StrEnum):
    HOSPITAL = "HOSPITAL"
    CLINIC = "CLINIC"
    DIAGNOSTIC_CENTER = "DIAGNOSTIC_CENTER"


class RoomType(StrEnum):
    CONSULTATION = "CONSULTATION"
    WARD = "WARD"
    PROCEDURE = "PROCEDURE"
    OTHER = "OTHER"


@lru_cache(maxsize=1)
def _known_timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def is_valid_timezone(name: str) -> bool:
    """True only for exact IANA names known to zoneinfo (membership check; never opens arbitrary paths)."""
    return name in _known_timezones()


def to_local(moment: datetime, timezone_name: str) -> datetime:
    """Convert a timezone-aware instant to the facility's local wall-clock time."""
    if moment.tzinfo is None:
        raise ValueError("naive datetimes are not allowed")
    return moment.astimezone(ZoneInfo(timezone_name))


def format_utc_offset(local: datetime) -> str:
    offset = local.utcoffset()
    if offset is None:
        raise ValueError("datetime has no UTC offset")
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"
