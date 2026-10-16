import uuid

import pytest

from tests.conftest import exception_payload


def _slots(client, headers, provider_id, facility_id, date_from, date_to=None):
    params = {"facility_id": facility_id, "date_from": date_from, "date_to": date_to or date_from}
    return client.get(f"/api/v1/providers/{provider_id}/slots", params=params, headers=headers)


def _starts(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [slot["start_utc"] for slot in response.json()["slots"]]


@pytest.fixture
def kolkata(facilities) -> str:
    return facilities.add("Asia/Kolkata")


@pytest.mark.parametrize("role", ["ADMIN", "RECEPTIONIST", "DOCTOR"])
def test_slots_in_facility_timezone(client, auth, provider_id, kolkata, create_working_hours, role) -> None:
    # Monday 09:00-10:00 Asia/Kolkata (UTC+05:30), 30-minute slots.
    create_working_hours(provider_id, kolkata, weekday=0, start_local_time="09:00", end_local_time="10:00")
    response = _slots(client, auth(role), provider_id, kolkata, "2026-04-06")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["timezone"] == "Asia/Kolkata" and body["advisory"] is True
    assert body["provider_id"] == provider_id and body["facility_id"] == kolkata
    assert body["date_from"] == body["date_to"] == "2026-04-06"
    assert body["slots"] == [
        {
            "start_utc": "2026-04-06T03:30:00Z",
            "end_utc": "2026-04-06T04:00:00Z",
            "start_local": "2026-04-06T09:00:00+05:30",
            "end_local": "2026-04-06T09:30:00+05:30",
            "source": "WORKING_HOURS",
        },
        {
            "start_utc": "2026-04-06T04:00:00Z",
            "end_utc": "2026-04-06T04:30:00Z",
            "start_local": "2026-04-06T09:30:00+05:30",
            "end_local": "2026-04-06T10:00:00+05:30",
            "source": "WORKING_HOURS",
        },
    ]


def test_read_only_cannot_query_slots(client, auth, provider_id, kolkata) -> None:
    assert _slots(client, auth("READ_ONLY"), provider_id, kolkata, "2026-04-06").status_code == 403


def test_spring_forward_dst_change_europe_london(
    client, admin, provider_id, facility_id, create_working_hours
) -> None:
    # Europe/London moves from GMT (UTC+0) to BST (UTC+1) on Sunday 2026-03-29.
    for weekday in (4, 0):  # Friday before, Monday after
        create_working_hours(
            provider_id, facility_id, weekday=weekday, start_local_time="09:00", end_local_time="10:00"
        )
    response = _slots(client, admin, provider_id, facility_id, "2026-03-27", "2026-03-30")
    assert _starts(response) == [
        "2026-03-27T09:00:00Z",
        "2026-03-27T09:30:00Z",
        "2026-03-30T08:00:00Z",
        "2026-03-30T08:30:00Z",
    ]
    local = [slot["start_local"] for slot in response.json()["slots"]]
    assert local == [
        "2026-03-27T09:00:00Z",
        "2026-03-27T09:30:00Z",
        "2026-03-30T09:00:00+01:00",
        "2026-03-30T09:30:00+01:00",
    ]


def test_fall_back_dst_change_europe_london(client, admin, provider_id, facility_id, create_working_hours):
    # BST -> GMT on Sunday 2026-10-25: 09:00 local is 08:00Z before and 09:00Z after.
    for weekday in (4, 0):
        create_working_hours(
            provider_id, facility_id, weekday=weekday, start_local_time="09:00", end_local_time="09:30"
        )
    response = _slots(client, admin, provider_id, facility_id, "2026-10-23", "2026-10-26")
    assert _starts(response) == ["2026-10-23T08:00:00Z", "2026-10-26T09:00:00Z"]


def test_rules_on_the_dst_change_night_skip_missing_local_times(
    client, admin, provider_id, facility_id, create_working_hours
) -> None:
    # 01:00-02:00 local does not exist on 2026-03-29; only real, full-length slots are returned.
    create_working_hours(
        provider_id, facility_id, weekday=6, start_local_time="00:00", end_local_time="03:00"
    )
    response = _slots(client, admin, provider_id, facility_id, "2026-03-29")
    # 00:30-01:00 ends at a non-existent local time, so it is skipped too.
    assert _starts(response) == ["2026-03-29T00:00:00Z", "2026-03-29T01:00:00Z", "2026-03-29T01:30:00Z"]
    assert [slot["start_local"][11:16] for slot in response.json()["slots"]] == ["00:00", "02:00", "02:30"]


def test_exceptions_remove_slots(
    client, admin, facilities, provider_id, kolkata, create_working_hours, create_exception
) -> None:
    create_working_hours(provider_id, kolkata, weekday=0, start_local_time="09:00", end_local_time="12:00")
    # 09:30-10:15 local (04:00Z-04:45Z) removes the 09:30 and 10:00 slots (partial overlap counts).
    create_exception(
        provider_id,
        facility_id=kolkata,
        type="BLOCKED",
        reason_code="ADMIN_BLOCK",
        starts_at="2026-04-06T04:00:00Z",
        ends_at="2026-04-06T04:45:00Z",
    )
    # A global exception (no facility) also applies: removes 11:30 local (06:00Z).
    create_exception(provider_id, starts_at="2026-04-06T06:00:00Z", ends_at="2026-04-06T06:30:00Z")
    # Exceptions at another facility, for another provider, or deactivated do not apply.
    create_exception(
        provider_id,
        facility_id=facilities.add("Asia/Kolkata"),
        starts_at="2026-04-06T03:30:00Z",
        ends_at="2026-04-06T04:00:00Z",
    )
    create_exception(str(uuid.uuid4()), starts_at="2026-04-06T05:00:00Z", ends_at="2026-04-06T05:30:00Z")
    deactivated = create_exception(
        provider_id, starts_at="2026-04-06T05:00:00Z", ends_at="2026-04-06T05:30:00Z"
    )
    assert client.delete(f"/api/v1/exceptions/{deactivated['id']}", headers=admin).status_code == 204

    response = _slots(client, admin, provider_id, kolkata, "2026-04-06")
    assert _starts(response) == ["2026-04-06T03:30:00Z", "2026-04-06T05:00:00Z", "2026-04-06T05:30:00Z"]


def test_holiday_removes_whole_day(
    client, admin, provider_id, kolkata, create_working_hours, create_exception
):
    create_working_hours(provider_id, kolkata, weekday=0)
    create_exception(
        provider_id,
        type="HOLIDAY",
        reason_code="PUBLIC_HOLIDAY",
        starts_at="2026-04-05T18:30:00Z",
        ends_at="2026-04-06T18:30:00Z",
    )
    assert _starts(_slots(client, admin, provider_id, kolkata, "2026-04-06")) == []
    assert len(_starts(_slots(client, admin, provider_id, kolkata, "2026-04-13"))) == 6


def test_extra_hours_add_slots(
    client, admin, facilities, provider_id, kolkata, create_working_hours, create_exception
) -> None:
    create_working_hours(provider_id, kolkata, weekday=0, start_local_time="09:00", end_local_time="10:00")
    # Tuesday has no working hours; EXTRA_HOURS adds 15-minute slots (configured default).
    create_exception(
        provider_id,
        facility_id=kolkata,
        type="EXTRA_HOURS",
        reason_code="CLINIC_COVER",
        starts_at="2026-04-07T08:30:00Z",
        ends_at="2026-04-07T09:15:00Z",
    )
    # Monday: extra hours right after the regular window, overlapping one regular slot (de-duplicated).
    create_exception(
        provider_id,
        facility_id=kolkata,
        type="EXTRA_HOURS",
        reason_code="CLINIC_COVER",
        starts_at="2026-04-06T04:00:00Z",
        ends_at="2026-04-06T04:30:00Z",
    )
    # Extra hours at another facility do not add slots here.
    create_exception(
        provider_id,
        facility_id=facilities.add("Asia/Kolkata"),
        type="EXTRA_HOURS",
        reason_code="CLINIC_COVER",
        starts_at="2026-04-07T10:00:00Z",
        ends_at="2026-04-07T11:00:00Z",
    )

    body = _slots(client, admin, provider_id, kolkata, "2026-04-06", "2026-04-07").json()
    assert [(slot["start_utc"], slot["end_utc"], slot["source"]) for slot in body["slots"]] == [
        ("2026-04-06T03:30:00Z", "2026-04-06T04:00:00Z", "WORKING_HOURS"),
        ("2026-04-06T04:00:00Z", "2026-04-06T04:15:00Z", "EXTRA_HOURS"),
        ("2026-04-06T04:00:00Z", "2026-04-06T04:30:00Z", "WORKING_HOURS"),
        ("2026-04-06T04:15:00Z", "2026-04-06T04:30:00Z", "EXTRA_HOURS"),
        ("2026-04-07T08:30:00Z", "2026-04-07T08:45:00Z", "EXTRA_HOURS"),
        ("2026-04-07T08:45:00Z", "2026-04-07T09:00:00Z", "EXTRA_HOURS"),
        ("2026-04-07T09:00:00Z", "2026-04-07T09:15:00Z", "EXTRA_HOURS"),
    ]


def test_blocking_exception_also_removes_extra_hours(client, admin, provider_id, kolkata, create_exception):
    create_exception(
        provider_id,
        facility_id=kolkata,
        type="EXTRA_HOURS",
        reason_code="COVER",
        starts_at="2026-04-07T08:30:00Z",
        ends_at="2026-04-07T09:00:00Z",
    )
    create_exception(
        provider_id, **exception_payload(starts_at="2026-04-07T08:30:00Z", ends_at="2026-04-07T08:45:00Z")
    )
    assert _starts(_slots(client, admin, provider_id, kolkata, "2026-04-07")) == ["2026-04-07T08:45:00Z"]


def test_validity_window_and_inactive_rules(
    client, admin, provider_id, kolkata, create_working_hours
) -> None:
    create_working_hours(
        provider_id,
        kolkata,
        weekday=0,
        start_local_time="09:00",
        end_local_time="09:30",
        valid_from="2026-04-13",
        valid_to="2026-04-20",
    )
    inactive = create_working_hours(
        provider_id, kolkata, weekday=0, start_local_time="14:00", end_local_time="14:30"
    )
    client.delete(f"/api/v1/working-hours/{inactive['id']}", headers=admin)

    response = _slots(client, admin, provider_id, kolkata, "2026-04-06", "2026-04-19")
    assert _starts(response) == ["2026-04-13T03:30:00Z"]


def test_slot_query_writes_nothing(client, admin, provider_id, kolkata, create_working_hours, app) -> None:
    from sqlalchemy import func, select

    from app.models import AvailabilityException, WorkingHours

    create_working_hours(provider_id, kolkata, weekday=0)
    _slots(client, admin, provider_id, kolkata, "2026-04-06")
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(WorkingHours)) == 1
        assert session.scalar(select(func.count()).select_from(AvailabilityException)) == 0


def test_fourteen_day_range_is_allowed(client, admin, provider_id, kolkata, create_working_hours) -> None:
    create_working_hours(provider_id, kolkata, weekday=0, start_local_time="09:00", end_local_time="09:30")
    assert len(_starts(_slots(client, admin, provider_id, kolkata, "2026-04-06", "2026-04-19"))) == 2


@pytest.mark.parametrize(
    ("date_from", "date_to", "message"),
    [
        ("2026-04-01", "2026-04-15", "The date range may span at most 14 days"),
        ("2026-04-02", "2026-04-01", "date_to must be on or after date_from"),
    ],
)
def test_invalid_date_range_is_422(
    client, admin, facilities, provider_id, kolkata, date_from, date_to, message
):
    response = _slots(client, admin, provider_id, kolkata, date_from, date_to)
    assert response.status_code == 422
    assert response.json()["error"] == {"code": "validation_error", "message": message}
    assert facilities.calls == []


@pytest.mark.parametrize(
    "params",
    [{"date_from": "2026-04-06", "date_to": "2026-04-06"}, {"facility_id": "x", "date_from": "2026-04-06"}],
    ids=["missing-facility", "bad-facility-and-missing-date"],
)
def test_missing_or_invalid_query_params_are_422(client, admin, provider_id, params) -> None:
    response = client.get(f"/api/v1/providers/{provider_id}/slots", params=params, headers=admin)
    assert response.status_code == 422


def test_slots_unknown_facility_is_404(client, admin, provider_id) -> None:
    response = _slots(client, admin, provider_id, str(uuid.uuid4()), "2026-04-06")
    assert response.status_code == 404
    assert response.json()["error"] == {"code": "not_found", "message": "Facility not found"}


def test_slots_facility_unavailable_is_503(client, admin, facilities, provider_id, kolkata) -> None:
    facilities.unavailable = True
    response = _slots(client, admin, provider_id, kolkata, "2026-04-06")
    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "service_unavailable",
        "message": "Facility service is unavailable; try again later",
    }


def test_slots_inactive_facility_is_409(client, admin, facilities, provider_id) -> None:
    inactive = facilities.add("Asia/Kolkata", is_active=False)
    assert _slots(client, admin, provider_id, inactive, "2026-04-06").status_code == 409


@pytest.mark.parametrize(
    ("date_from", "date_to"),
    [("9999-12-31", "9999-12-31"), ("0001-01-01", "0001-01-02"), ("1899-12-31", "1900-01-01")],
    ids=["date-max", "date-min", "before-1900"],
)
def test_out_of_range_dates_are_422(
    client, admin, facilities, provider_id, kolkata, date_from, date_to
) -> None:
    response = _slots(client, admin, provider_id, kolkata, date_from, date_to)
    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "validation_error",
        "message": "Dates must be between 1900-01-01 and 9998-12-31",
    }
    assert facilities.calls == []
