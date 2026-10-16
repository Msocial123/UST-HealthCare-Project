from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.domain.slots import (
    SlotSource,
    WeeklyRule,
    Window,
    compute_slots,
    extra_hours_slots,
    local_day_bounds,
    local_to_utc,
)

LONDON = ZoneInfo("Europe/London")


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def test_local_to_utc_handles_gap_and_fold() -> None:
    assert local_to_utc(date(2026, 3, 29), time(1, 30), LONDON) is None  # does not exist
    assert local_to_utc(date(2026, 3, 29), time(2, 30), LONDON) == _utc("2026-03-29T01:30")
    assert local_to_utc(date(2026, 10, 25), time(1, 30), LONDON) == _utc("2026-10-25T00:30")  # first (BST)
    assert local_to_utc(date(2026, 10, 25), time(9, 0), LONDON) == _utc("2026-10-25T09:00")


def test_fall_back_night_skips_slots_that_straddle_the_repeat() -> None:
    rule = WeeklyRule(6, time(0, 30), time(2, 30), 30, date(2026, 1, 1), None)
    slots = compute_slots(
        rules=[rule],
        extra_windows=[],
        blocks=[],
        zone=LONDON,
        date_from=date(2026, 10, 25),
        date_to=date(2026, 10, 25),
        extra_slot_minutes=15,
    )
    assert [(slot.start_utc, slot.end_utc) for slot in slots] == [
        (_utc("2026-10-24T23:30"), _utc("2026-10-25T00:00")),
        (_utc("2026-10-25T00:00"), _utc("2026-10-25T00:30")),
        (_utc("2026-10-25T02:00"), _utc("2026-10-25T02:30")),
    ]
    assert all((slot.end_utc - slot.start_utc).total_seconds() == 1800 for slot in slots)


def test_local_day_bounds_cover_dst_day() -> None:
    bounds = local_day_bounds(date(2026, 3, 29), date(2026, 3, 29), LONDON)
    assert bounds == Window(_utc("2026-03-29T00:00"), _utc("2026-03-29T23:00"))


def test_extra_hours_are_clipped_and_aligned_to_window_start() -> None:
    bounds = Window(_utc("2026-04-07T00:00"), _utc("2026-04-08T00:00"))
    window = Window(_utc("2026-04-06T23:50"), _utc("2026-04-07T00:40"))
    slots = extra_hours_slots([window], bounds, 15)
    assert [slot.start_utc for slot in slots] == [_utc("2026-04-07T00:05"), _utc("2026-04-07T00:20")]
    assert {slot.source for slot in slots} == {SlotSource.EXTRA_HOURS}


def test_long_extra_hours_window_does_not_iterate_from_its_start() -> None:
    bounds = Window(_utc("2026-04-07T00:00"), _utc("2026-04-07T01:00"))
    window = Window(_utc("2025-04-08T00:00"), _utc("2026-04-07T00:30"))
    assert len(extra_hours_slots([window], bounds, 5)) == 6


def test_extra_hours_slots_never_end_after_the_queried_dates() -> None:
    bounds = Window(_utc("2026-04-07T00:00"), _utc("2026-04-08T00:00"))
    window = Window(_utc("2026-04-07T23:15"), _utc("2026-04-08T00:30"))
    slots = extra_hours_slots([window], bounds, 30)
    assert [(slot.start_utc, slot.end_utc) for slot in slots] == [
        (_utc("2026-04-07T23:15"), _utc("2026-04-07T23:45"))
    ]
