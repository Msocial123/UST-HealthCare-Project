import uuid

import pytest

from tests.conftest import exception_payload

RANGE = {"from": "2026-04-01T00:00:00Z", "to": "2026-05-01T00:00:00Z"}


def _url(provider_id: str) -> str:
    return f"/api/v1/providers/{provider_id}/exceptions"


@pytest.mark.parametrize("role", ["ADMIN", "RECEPTIONIST"])
def test_create_exception(client, auth, facilities, provider_id, role) -> None:
    response = client.post(_url(provider_id), json=exception_payload(), headers=auth(role))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["provider_id"] == provider_id and body["facility_id"] is None
    assert body["type"] == "LEAVE" and body["reason_code"] == "ANNUAL_LEAVE" and body["is_active"] is True
    assert body["starts_at"] == "2026-04-06T09:00:00Z" and body["ends_at"] == "2026-04-06T10:00:00Z"
    assert facilities.calls == []  # global exceptions need no facility lookup


def test_offsets_are_normalised_to_utc_and_reason_upper_cased(
    client, admin, provider_id, facility_id
) -> None:
    payload = exception_payload(
        facility_id=facility_id,
        starts_at="2026-04-06T10:00:00+01:00",
        ends_at="2026-04-06T15:30:00+05:30",
        type="BLOCKED",
        reason_code="training_day",
    )
    body = client.post(_url(provider_id), json=payload, headers=admin).json()
    assert body["starts_at"] == "2026-04-06T09:00:00Z" and body["ends_at"] == "2026-04-06T10:00:00Z"
    assert body["reason_code"] == "TRAINING_DAY" and body["facility_id"] == facility_id


def test_extra_hours_exception_with_facility(client, admin, provider_id, facility_id) -> None:
    payload = exception_payload(facility_id=facility_id, type="EXTRA_HOURS", reason_code="CLINIC_COVER")
    assert client.post(_url(provider_id), json=payload, headers=admin).status_code == 201


@pytest.mark.parametrize(
    "overrides",
    [
        {"ends_at": "2026-04-06T08:00:00Z"},
        {"ends_at": "2026-04-06T09:00:00Z"},
        {"starts_at": "2026-04-06T09:00:00"},
        {"ends_at": "2027-06-01T00:00:00Z"},
        {"type": "EXTRA_HOURS"},
        {"type": "SICK_NOTE"},
        {"reason_code": "Patient follow-up with notes"},
        {"reason_code": "X"},
        {"reason_code": "A" * 33},
        {"notes": "free text is not accepted"},
    ],
    ids=[
        "ends-before-starts",
        "zero-length",
        "naive-datetime",
        "longer-than-366-days",
        "extra-hours-without-facility",
        "unknown-type",
        "free-text-reason",
        "reason-too-short",
        "reason-too-long",
        "extra-field",
    ],
)
def test_invalid_exception_is_422(client, admin, provider_id, overrides) -> None:
    response = client.post(_url(provider_id), json=exception_payload(**overrides), headers=admin)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_exception_unknown_facility_is_404(client, admin, provider_id) -> None:
    payload = exception_payload(facility_id=str(uuid.uuid4()))
    assert client.post(_url(provider_id), json=payload, headers=admin).status_code == 404


def test_exception_facility_unavailable_is_503(client, admin, facilities, provider_id, facility_id) -> None:
    facilities.unavailable = True
    response = client.post(_url(provider_id), json=exception_payload(facility_id=facility_id), headers=admin)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_extra_hours_at_inactive_facility_is_409(client, admin, facilities, provider_id) -> None:
    inactive = facilities.add(is_active=False)
    extra = exception_payload(facility_id=inactive, type="EXTRA_HOURS", reason_code="COVER")
    assert client.post(_url(provider_id), json=extra, headers=admin).status_code == 409
    leave = exception_payload(facility_id=inactive)
    assert client.post(_url(provider_id), json=leave, headers=admin).status_code == 201


def test_list_exceptions_in_range(
    client, auth, facilities, provider_id, facility_id, create_exception
) -> None:
    other_facility = facilities.add()
    inside = create_exception(provider_id)
    spanning = create_exception(provider_id, starts_at="2026-03-30T00:00:00Z", ends_at="2026-04-02T00:00:00Z")
    at_facility = create_exception(
        provider_id,
        facility_id=facility_id,
        starts_at="2026-04-10T09:00:00Z",
        ends_at="2026-04-10T10:00:00Z",
        type="HOLIDAY",
        reason_code="PUBLIC_HOLIDAY",
    )
    create_exception(
        provider_id,
        facility_id=other_facility,
        starts_at="2026-04-11T09:00:00Z",
        ends_at="2026-04-11T10:00:00Z",
    )
    create_exception(provider_id, starts_at="2026-05-02T09:00:00Z", ends_at="2026-05-02T10:00:00Z")
    create_exception(str(uuid.uuid4()))

    for role in ("ADMIN", "RECEPTIONIST", "DOCTOR", "READ_ONLY"):
        response = client.get(_url(provider_id), params=RANGE, headers=auth(role))
        assert response.status_code == 200
        assert response.json()["total"] == 4

    body = client.get(_url(provider_id), params=RANGE, headers=auth()).json()
    assert [item["id"] for item in body["items"]][:2] == [spanning["id"], inside["id"]]

    filtered = client.get(
        _url(provider_id), params={**RANGE, "facility_id": facility_id}, headers=auth()
    ).json()
    assert {item["id"] for item in filtered["items"]} == {inside["id"], spanning["id"], at_facility["id"]}


@pytest.mark.parametrize(
    "params",
    [
        {"from": "2026-04-02T00:00:00Z", "to": "2026-04-01T00:00:00Z"},
        {"from": "2026-04-01T00:00:00Z", "to": "2026-04-01T00:00:00Z"},
        {"from": "2026-01-01T00:00:00Z", "to": "2027-06-01T00:00:00Z"},
        {"from": "2026-04-01T00:00:00", "to": "2026-04-02T00:00:00Z"},
        {"to": "2026-04-02T00:00:00Z"},
        {"from": "2026-04-01T00:00:00Z"},
    ],
    ids=["to-before-from", "empty", "too-long", "naive", "missing-from", "missing-to"],
)
def test_invalid_list_range_is_422(client, admin, provider_id, params) -> None:
    response = client.get(_url(provider_id), params=params, headers=admin)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_update_exception(client, auth, provider_id, create_exception) -> None:
    exception = create_exception(provider_id)
    response = client.patch(
        f"/api/v1/exceptions/{exception['id']}",
        json={"ends_at": "2026-04-06T12:00:00Z", "type": "BLOCKED", "reason_code": "ADMIN_BLOCK"},
        headers=auth("RECEPTIONIST"),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ends_at"] == "2026-04-06T12:00:00Z" and body["type"] == "BLOCKED"
    assert body["reason_code"] == "ADMIN_BLOCK"


@pytest.mark.parametrize(
    "body",
    [{"ends_at": "2026-04-06T08:00:00Z"}, {"type": "EXTRA_HOURS"}, {"type": None}, {"facility_id": None}],
    ids=["ends-before-existing-start", "extra-hours-without-facility", "null", "immutable-facility"],
)
def test_invalid_exception_update_is_422(client, admin, provider_id, create_exception, body) -> None:
    exception = create_exception(provider_id)
    response = client.patch(f"/api/v1/exceptions/{exception['id']}", json=body, headers=admin)
    assert response.status_code == 422


def test_deactivate_exception(client, admin, provider_id, create_exception) -> None:
    exception = create_exception(provider_id)
    assert client.delete(f"/api/v1/exceptions/{exception['id']}", headers=admin).status_code == 204
    assert client.get(_url(provider_id), params=RANGE, headers=admin).json()["total"] == 0
    inactive = client.get(_url(provider_id), params={**RANGE, "active": False}, headers=admin).json()
    assert [item["id"] for item in inactive["items"]] == [exception["id"]]
    assert inactive["items"][0]["is_active"] is False
    reactivated = client.patch(
        f"/api/v1/exceptions/{exception['id']}", json={"is_active": True}, headers=admin
    )
    assert reactivated.json()["is_active"] is True


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_unknown_exception_is_404(client, admin, method) -> None:
    body = {"reason_code": "OTHER"} if method == "patch" else None
    response = client.request(method, f"/api/v1/exceptions/{uuid.uuid4()}", json=body, headers=admin)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
