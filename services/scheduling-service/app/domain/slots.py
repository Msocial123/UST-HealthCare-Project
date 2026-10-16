"""Pure, DST-aware advisory slot generation.

Working hours are facility-local wall-clock times. Each slot boundary is converted to UTC with the
facility's IANA timezone, so a 09:00 rule maps to different UTC instants either side of a DST change.
Slots touching a local time that does not exist (spring-forward gap) are skipped; ambiguous local
times (autumn fall-back) resolve to their first occurrence, and a slot whose real elapsed length would
differ from slot_minutes because it straddles a transition is skipped. Nothing here reserves or locks
a slot.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo


class SlotSource(StrEnum):
    WORKING_HOURS = "WORKING_HOURS"
    EXTRA_HOURS = "EXTRA_HOURS"


@dataclass(frozen=True)
class WeeklyRule:
    weekday: int
    start_local_time: time
    end_local_time: time
    slot_minutes: int
    valid_from: date
    valid_to: date | None

    def applies_on(self, day: date) -> bool:
        return (
            day.weekday() == self.weekday
            and self.valid_from <= day
            and (self.valid_to is None or day <= self.valid_to)
        )


@dataclass(frozen=True)
class Window:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class Slot:
    start_utc: datetime
    end_utc: datetime
    source: SlotSource


def local_to_utc(day: date, wall_time: time, zone: ZoneInfo) -> datetime | None:
    """Convert a local wall-clock time to UTC, or None if it does not exist (DST gap)."""
    naive = datetime.combine(day, wall_time)
    utc = naive.replace(tzinfo=zone, fold=0).astimezone(UTC)
    if utc.astimezone(zone).replace(tzinfo=None) != naive:
        return None
    return utc


def local_day_bounds(date_from: date, date_to: date, zone: ZoneInfo) -> Window:
    """UTC instants of local midnight at the start of date_from and the end of date_to."""
    start = datetime.combine(date_from, time()).replace(tzinfo=zone).astimezone(UTC)
    end = datetime.combine(date_to + timedelta(days=1), time()).replace(tzinfo=zone).astimezone(UTC)
    return Window(start, end)


def iter_days(date_from: date, date_to: date) -> Iterable[date]:
    for offset in range((date_to - date_from).days + 1):
        yield date_from + timedelta(days=offset)


def working_hours_slots(
    rules: Iterable[WeeklyRule], zone: ZoneInfo, date_from: date, date_to: date
) -> list[Slot]:
    rules = list(rules)
    slots: list[Slot] = []
    for day in iter_days(date_from, date_to):
        for rule in rules:
            if not rule.applies_on(day):
                continue
            step = timedelta(minutes=rule.slot_minutes)
            cursor = datetime.combine(day, rule.start_local_time)
            end = datetime.combine(day, rule.end_local_time)
            while cursor + step <= end:
                start_utc = local_to_utc(day, cursor.time(), zone)
                end_utc = local_to_utc(day, (cursor + step).time(), zone)
                if start_utc is not None and end_utc is not None and end_utc - start_utc == step:
                    slots.append(Slot(start_utc, end_utc, SlotSource.WORKING_HOURS))
                cursor += step
    return slots


def extra_hours_slots(windows: Iterable[Window], bounds: Window, slot_minutes: int) -> list[Slot]:
    """Slots stepped in absolute time from each EXTRA_HOURS window start, limited to the query range."""
    step = timedelta(minutes=slot_minutes)
    slots: list[Slot] = []
    for window in windows:
        cursor = window.starts_at
        if cursor < bounds.starts_at:
            cursor += step * math.ceil((bounds.starts_at - cursor) / step)
        while cursor + step <= window.ends_at and cursor + step <= bounds.ends_at:
            slots.append(Slot(cursor, cursor + step, SlotSource.EXTRA_HOURS))
            cursor += step
    return slots


def remove_blocked(slots: Iterable[Slot], blocks: Iterable[Window]) -> list[Slot]:
    blocks = list(blocks)
    return [
        slot
        for slot in slots
        if not any(slot.start_utc < block.ends_at and block.starts_at < slot.end_utc for block in blocks)
    ]


def merge_slots(slots: Iterable[Slot]) -> list[Slot]:
    """De-duplicate identical intervals (working hours win over extra hours) and sort by start time."""
    unique: dict[tuple[datetime, datetime], Slot] = {}
    for slot in slots:
        key = (slot.start_utc, slot.end_utc)
        if key not in unique or slot.source == SlotSource.WORKING_HOURS:
            unique[key] = slot
    return sorted(unique.values(), key=lambda slot: (slot.start_utc, slot.end_utc))


def compute_slots(
    *,
    rules: Iterable[WeeklyRule],
    extra_windows: Iterable[Window],
    blocks: Iterable[Window],
    zone: ZoneInfo,
    date_from: date,
    date_to: date,
    extra_slot_minutes: int,
) -> list[Slot]:
    bounds = local_day_bounds(date_from, date_to, zone)
    candidates = working_hours_slots(rules, zone, date_from, date_to)
    candidates += extra_hours_slots(extra_windows, bounds, extra_slot_minutes)
    return merge_slots(remove_blocked(candidates, blocks))
