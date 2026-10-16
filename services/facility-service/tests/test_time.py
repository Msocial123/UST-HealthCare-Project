"""UTC storage and facility local-time conversion, using an injected clock."""

import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.domain.facilities import format_utc_offset, to_local
from app.models.facility import Facility

FIXED_UTC = datetime(2026, 1, 15, 6, 30, tzinfo=UTC)


def test_timestamps_stored_and_returned_in_utc_and_local_time_from_timezone(
    app, client, admin, create_facility
) -> None:
    # A non-UTC clock proves values are normalized to UTC on the way into the database.
    app.state.clock = lambda: FIXED_UTC.astimezone(timezone(timedelta(hours=-7)))
    facility = create_facility(timezone="Asia/Kolkata")
    assert facility["created_at"] == facility["updated_at"] == "2026-01-15T06:30:00Z"

    with app.state.session_factory() as session:
        stored = session.scalars(select(Facility).where(Facility.id == uuid.UUID(facility["id"]))).one()
        assert stored.created_at == FIXED_UTC
        assert stored.created_at.utcoffset() == timedelta(0)

    detail = client.get(f"/api/v1/facilities/{facility['id']}", headers=admin).json()
    assert detail["current_local_time"] == "2026-01-15T12:00:00+05:30"
    assert detail["utc_offset"] == "+05:30"
    assert detail["created_at"] == "2026-01-15T06:30:00Z"

    client.patch(f"/api/v1/facilities/{facility['id']}", json={"timezone": "America/New_York"}, headers=admin)
    detail = client.get(f"/api/v1/facilities/{facility['id']}", headers=admin).json()
    assert detail["current_local_time"] == "2026-01-15T01:30:00-05:00"
    assert detail["utc_offset"] == "-05:00"


def test_department_and_room_timestamps_are_utc(app, admin, create_facility, create_department, create_room):
    app.state.clock = lambda: FIXED_UTC
    department = create_department(create_facility()["id"])
    room = create_room(department["id"])
    for entity in (department, room):
        assert entity["created_at"] == entity["updated_at"] == "2026-01-15T06:30:00Z"


@pytest.mark.parametrize(
    ("moment", "tz", "expected_local", "expected_offset"),
    [
        (datetime(2026, 7, 1, 12, 0, tzinfo=UTC), "America/New_York", "2026-07-01T08:00:00-04:00", "-04:00"),
        (datetime(2026, 1, 1, 12, 0, tzinfo=UTC), "America/New_York", "2026-01-01T07:00:00-05:00", "-05:00"),
        (datetime(2026, 1, 1, 12, 0, tzinfo=UTC), "Asia/Kathmandu", "2026-01-01T17:45:00+05:45", "+05:45"),
        (datetime(2026, 1, 1, 12, 0, tzinfo=UTC), "UTC", "2026-01-01T12:00:00+00:00", "+00:00"),
    ],
)
def test_to_local_handles_dst_and_fractional_offsets(moment, tz, expected_local, expected_offset) -> None:
    local = to_local(moment, tz)
    assert local.isoformat() == expected_local
    assert format_utc_offset(local) == expected_offset


def test_to_local_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="naive"):
        to_local(datetime(2026, 1, 1, 12, 0), "UTC")  # noqa: DTZ001


def test_database_type_rejects_naive_datetimes(app, create_facility) -> None:
    facility_id = create_facility()["id"]
    with app.state.session_factory() as session:
        stored = session.scalars(select(Facility).where(Facility.id == uuid.UUID(facility_id))).one()
        stored.updated_at = datetime(2026, 1, 1, 12, 0)  # noqa: DTZ001
        with pytest.raises(Exception, match="naive|timezone"):
            session.commit()
