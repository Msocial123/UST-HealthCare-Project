import uuid

import pytest

from tests.conftest import working_hours_payload


def _url(provider_id: str) -> str:
    return f"/api/v1/providers/{provider_id}/working-hours"


def test_create_working_hours(client, admin, facilities, provider_id, facility_id) -> None:
    response = client.post(_url(provider_id), json=working_hours_payload(facility_id), headers=admin)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["provider_id"] == provider_id and body["facility_id"] == facility_id
    assert body["weekday"] == 0 and body["slot_minutes"] == 30
    assert body["start_local_time"] == "09:00:00" and body["end_local_time"] == "12:00:00"
    assert body["valid_from"] == "2026-01-01" and body["valid_to"] is None
    assert body["is_active"] is True
    assert body["created_at"].endswith("Z")
    # The facility was checked through the FacilityClient contract with the caller's token.
    assert facilities.calls[-1][0] == uuid.UUID(facility_id)
    assert facilities.calls[-1][1] == admin["Authorization"].removeprefix("Bearer ")


def test_list_working_hours_with_filters(
    client, auth, facilities, provider_id, facility_id, create_working_hours
) -> None:
    other_facility = facilities.add("Asia/Kolkata")
    create_working_hours(provider_id, facility_id, weekday=0)
    create_working_hours(provider_id, facility_id, weekday=2)
    create_working_hours(provider_id, other_facility, weekday=0)
    create_working_hours(str(uuid.uuid4()), facility_id, weekday=0)

    for role in ("ADMIN", "RECEPTIONIST", "DOCTOR", "READ_ONLY"):
        response = client.get(_url(provider_id), headers=auth(role))
        assert response.status_code == 200
        assert response.json()["total"] == 3

    by_facility = client.get(_url(provider_id), params={"facility_id": facility_id}, headers=auth()).json()
    assert by_facility["total"] == 2
    by_weekday = client.get(_url(provider_id), params={"weekday": 2}, headers=auth()).json()
    assert [item["weekday"] for item in by_weekday["items"]] == [2]
    page = client.get(_url(provider_id), params={"limit": 1, "offset": 1}, headers=auth()).json()
    assert len(page["items"]) == 1 and page["total"] == 3 and page["limit"] == 1 and page["offset"] == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_local_time": "10:00", "end_local_time": "13:00"},
        {"start_local_time": "08:00", "end_local_time": "09:30"},
        {"start_local_time": "08:00", "end_local_time": "18:00"},
        {"start_local_time": "09:00", "end_local_time": "12:00", "valid_from": "2026-06-01"},
    ],
    ids=["overlaps-end", "overlaps-start", "contains", "identical-later-validity"],
)
def test_overlapping_rule_is_409(client, admin, provider_id, facility_id, create_working_hours, overrides):
    existing = create_working_hours(provider_id, facility_id)
    response = client.post(
        _url(provider_id), json=working_hours_payload(facility_id, **overrides), headers=admin
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "conflict"
    assert error["details"] == {"conflicting_id": existing["id"]}


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_local_time": "12:00", "end_local_time": "15:00"},
        {"weekday": 1},
        {"valid_from": "2027-01-01"},
    ],
    ids=["adjacent", "other-weekday", "after-validity"],
)
def test_non_overlapping_rules_are_allowed(
    client, admin, provider_id, facility_id, create_working_hours, overrides
) -> None:
    create_working_hours(provider_id, facility_id, valid_to="2026-12-31")
    response = client.post(
        _url(provider_id), json=working_hours_payload(facility_id, **overrides), headers=admin
    )
    assert response.status_code == 201, response.text


def test_same_hours_at_other_facility_or_for_other_provider_are_allowed(
    client, admin, facilities, provider_id, facility_id, create_working_hours
) -> None:
    create_working_hours(provider_id, facility_id)
    other_facility = facilities.add("Europe/London")
    assert (
        client.post(_url(provider_id), json=working_hours_payload(other_facility), headers=admin).status_code
        == 201
    )
    other_provider = str(uuid.uuid4())
    assert (
        client.post(_url(other_provider), json=working_hours_payload(facility_id), headers=admin).status_code
        == 201
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_local_time": "12:00", "end_local_time": "09:00"},
        {"start_local_time": "09:00", "end_local_time": "09:00"},
        {"slot_minutes": 4},
        {"slot_minutes": 121},
        {"start_local_time": "09:00", "end_local_time": "09:20", "slot_minutes": 30},
        {"valid_from": "2026-05-01", "valid_to": "2026-04-30"},
        {"weekday": 7},
        {"weekday": -1},
        {"start_local_time": "09:00:00+01:00"},
        {"start_local_time": "09:00:30"},
        {"facility_id": "not-a-uuid"},
        {"unexpected": "field"},
    ],
    ids=[
        "end-before-start",
        "end-equals-start",
        "slot-too-short",
        "slot-too-long",
        "window-shorter-than-slot",
        "valid-to-before-from",
        "weekday-too-high",
        "weekday-negative",
        "time-with-offset",
        "time-with-seconds",
        "bad-facility-id",
        "extra-field",
    ],
)
def test_invalid_working_hours_are_422(
    client, admin, facilities, provider_id, facility_id, overrides
) -> None:
    response = client.post(
        _url(provider_id), json=working_hours_payload(facility_id, **overrides), headers=admin
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert facilities.calls == []


def test_end_before_start_has_clear_message(client, admin, provider_id, facility_id) -> None:
    payload = working_hours_payload(facility_id, start_local_time="12:00", end_local_time="09:00")
    details = client.post(_url(provider_id), json=payload, headers=admin).json()["error"]["details"]
    assert details[0]["msg"] == "end_local_time must be after start_local_time"
    assert details[0]["type"] == "invalid_rule"


def test_unknown_facility_is_404(client, admin, provider_id) -> None:
    response = client.post(_url(provider_id), json=working_hours_payload(str(uuid.uuid4())), headers=admin)
    assert response.status_code == 404
    assert response.json()["error"] == {"code": "not_found", "message": "Facility not found"}


def test_facility_service_unavailable_is_503(client, admin, facilities, provider_id, facility_id) -> None:
    facilities.unavailable = True
    response = client.post(_url(provider_id), json=working_hours_payload(facility_id), headers=admin)
    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "service_unavailable",
        "message": "Facility service is unavailable; try again later",
    }
    facilities.unavailable = False
    assert client.get(_url(provider_id), headers=admin).json()["total"] == 0


def test_inactive_facility_is_409(client, admin, facilities, provider_id) -> None:
    inactive = facilities.add("Europe/London", is_active=False)
    response = client.post(_url(provider_id), json=working_hours_payload(inactive), headers=admin)
    assert response.status_code == 409


def test_update_working_hours(client, admin, provider_id, facility_id, create_working_hours) -> None:
    rule = create_working_hours(provider_id, facility_id)
    response = client.patch(
        f"/api/v1/working-hours/{rule['id']}",
        json={"slot_minutes": 15, "end_local_time": "13:00", "valid_to": "2026-12-31"},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["slot_minutes"] == 15 and body["end_local_time"] == "13:00:00"
    assert body["valid_to"] == "2026-12-31"
    assert body["updated_at"] >= rule["updated_at"]

    cleared = client.patch(f"/api/v1/working-hours/{rule['id']}", json={"valid_to": None}, headers=admin)
    assert cleared.json()["valid_to"] is None


def test_update_into_overlap_is_409(client, admin, provider_id, facility_id, create_working_hours) -> None:
    create_working_hours(provider_id, facility_id, start_local_time="09:00", end_local_time="12:00")
    later = create_working_hours(provider_id, facility_id, start_local_time="13:00", end_local_time="16:00")
    response = client.patch(
        f"/api/v1/working-hours/{later['id']}", json={"start_local_time": "11:00"}, headers=admin
    )
    assert response.status_code == 409
    unchanged = client.get(_url(provider_id), headers=admin).json()["items"]
    assert {item["start_local_time"] for item in unchanged} == {"09:00:00", "13:00:00"}


@pytest.mark.parametrize(
    "body",
    [
        {"end_local_time": "08:00"},
        {"slot_minutes": 200},
        {"valid_to": "2025-01-01"},
        {"slot_minutes": None},
        {"facility_id": str(uuid.uuid4())},
    ],
    ids=["end-before-existing-start", "slot-range", "valid-to-before-from", "null", "immutable-facility"],
)
def test_invalid_update_is_422(client, admin, provider_id, facility_id, create_working_hours, body) -> None:
    rule = create_working_hours(provider_id, facility_id)
    response = client.patch(f"/api/v1/working-hours/{rule['id']}", json=body, headers=admin)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_deactivate_and_reactivate(client, admin, provider_id, facility_id, create_working_hours) -> None:
    rule = create_working_hours(provider_id, facility_id)
    response = client.delete(f"/api/v1/working-hours/{rule['id']}", headers=admin)
    assert response.status_code == 204 and response.content == b""
    assert client.delete(f"/api/v1/working-hours/{rule['id']}", headers=admin).status_code == 204

    listed = client.get(_url(provider_id), params={"active": False}, headers=admin).json()
    assert [item["id"] for item in listed["items"]] == [rule["id"]]
    assert client.get(_url(provider_id), params={"active": True}, headers=admin).json()["total"] == 0

    # A deactivated rule no longer blocks a replacement, and cannot be re-activated while overlapping.
    create_working_hours(provider_id, facility_id)
    reactivate = client.patch(f"/api/v1/working-hours/{rule['id']}", json={"is_active": True}, headers=admin)
    assert reactivate.status_code == 409
    moved = client.patch(
        f"/api/v1/working-hours/{rule['id']}",
        json={"is_active": True, "start_local_time": "13:00", "end_local_time": "15:00"},
        headers=admin,
    )
    assert moved.status_code == 200 and moved.json()["is_active"] is True


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_unknown_working_hours_is_404(client, admin, method) -> None:
    body = {"slot_minutes": 15} if method == "patch" else None
    response = client.request(method, f"/api/v1/working-hours/{uuid.uuid4()}", json=body, headers=admin)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_invalid_path_ids_are_422(client, admin) -> None:
    assert client.get("/api/v1/providers/not-a-uuid/working-hours", headers=admin).status_code == 422
    assert client.delete("/api/v1/working-hours/not-a-uuid", headers=admin).status_code == 422


def test_update_revalidates_against_current_values_not_stale_ones(
    app, admin, provider_id, facility_id, create_working_hours
) -> None:
    """Regression: a request that loaded a rule before a concurrent commit must not validate stale fields."""
    from datetime import UTC, datetime

    from app.schemas.working_hours import WorkingHoursUpdate
    from app.services.working_hours_service import WorkingHoursService

    monday = create_working_hours(
        provider_id, facility_id, weekday=0, start_local_time="09:00", end_local_time="10:00"
    )
    target = create_working_hours(
        provider_id, facility_id, weekday=1, start_local_time="11:00", end_local_time="12:00"
    )
    target_id = uuid.UUID(target["id"])

    def clock() -> datetime:
        return datetime.now(UTC)

    with app.state.session_factory() as stale, app.state.session_factory() as other:
        WorkingHoursService(stale, clock).get(target_id)  # request B loads Tuesday 11:00-12:00
        WorkingHoursService(other, clock).update(
            target_id, WorkingHoursUpdate(weekday=0)
        )  # request A commits
        with pytest.raises(Exception) as excinfo:
            WorkingHoursService(stale, clock).update(
                target_id, WorkingHoursUpdate(start_local_time="09:00", end_local_time="10:00")
            )
    assert getattr(excinfo.value, "status_code", None) == 409
    assert excinfo.value.details == {"conflicting_id": monday["id"]}
