import uuid

import pytest

from tests.conftest import facility_payload

BASE = "/api/v1/facilities"


def _error_code(response) -> str:
    return response.json()["error"]["code"]


def test_create_facility_normalizes_and_returns_fields(client, admin) -> None:
    payload = facility_payload(code="nhg-main", country_code="in")
    response = client.post(BASE, json=payload, headers=admin)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["code"] == "NHG-MAIN"
    assert body["country_code"] == "IN"
    assert body["facility_type"] == "HOSPITAL"
    assert body["timezone"] == "Asia/Kolkata"
    assert body["is_active"] is True
    uuid.UUID(body["id"])


def test_duplicate_facility_code_is_409(client, admin, create_facility) -> None:
    create_facility(code="DUP-01")
    response = client.post(BASE, json=facility_payload(code="dup-01"), headers=admin)
    assert response.status_code == 409
    assert _error_code(response) == "conflict"


@pytest.mark.parametrize("timezone", ["Mars/Olympus", "asia/kolkata", "Asia/Kolkata/../../etc", "IST", ""])
def test_invalid_timezone_is_422_and_not_echoed(client, admin, timezone) -> None:
    response = client.post(BASE, json=facility_payload(timezone=timezone), headers=admin)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    if timezone:
        assert timezone not in response.text
        assert body["error"]["details"][0]["msg"].startswith("Must be a valid IANA timezone name")


@pytest.mark.parametrize(
    "overrides",
    [
        {"facility_type": "PHARMACY"},
        {"code": "x"},
        {"code": "BAD CODE"},
        {"country_code": "IND"},
        {"main_phone": "call-me"},
        {"name": ""},
        {"is_active": False},
        {"unexpected": "field"},
    ],
    ids=[
        "bad-type",
        "short-code",
        "code-space",
        "country-3",
        "bad-phone",
        "empty-name",
        "is-active",
        "extra",
    ],
)
def test_invalid_facility_payloads_are_422(client, admin, overrides) -> None:
    response = client.post(BASE, json=facility_payload(**overrides), headers=admin)
    assert response.status_code == 422
    assert _error_code(response) == "validation_error"


def test_missing_required_field_is_422(client, admin) -> None:
    payload = facility_payload()
    del payload["timezone"]
    assert client.post(BASE, json=payload, headers=admin).status_code == 422


def test_get_facility_includes_timezone_and_local_time(client, admin, create_facility) -> None:
    facility = create_facility()
    response = client.get(f"{BASE}/{facility['id']}", headers=admin)
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "Asia/Kolkata"
    assert body["utc_offset"] == "+05:30"
    assert body["current_local_time"].endswith("+05:30")


def test_get_missing_facility_is_404(client, admin) -> None:
    response = client.get(f"{BASE}/{uuid.uuid4()}", headers=admin)
    assert response.status_code == 404
    assert _error_code(response) == "not_found"


def test_invalid_facility_id_is_422(client, admin) -> None:
    assert client.get(f"{BASE}/not-a-uuid", headers=admin).status_code == 422


def test_list_search_and_filters(client, admin, create_facility) -> None:
    alpha = create_facility(code="ALPHA", name="Alpha Hospital", city="Northtown")
    beta = create_facility(code="BETA", name="Beta Clinic", facility_type="CLINIC", city="Southtown")
    gamma = create_facility(
        code="GAMMA", name="Gamma Imaging", facility_type="DIAGNOSTIC_CENTER", city="Northtown"
    )
    client.post(f"{BASE}/{gamma['id']}/deactivate", headers=admin)

    def ids(**params):
        response = client.get(BASE, params=params, headers=admin)
        assert response.status_code == 200, response.text
        return [item["id"] for item in response.json()["items"]]

    assert ids() == [alpha["id"], beta["id"], gamma["id"]]
    assert ids(search="clinic") == [beta["id"]]
    assert ids(search="beta") == [beta["id"]]
    assert ids(search="northtown") == [alpha["id"], gamma["id"]]
    assert ids(search="%") == []
    assert ids(type="CLINIC") == [beta["id"]]
    assert ids(active="false") == [gamma["id"]]
    assert ids(active="true", search="northtown") == [alpha["id"]]
    assert client.get(BASE, params={"type": "PHARMACY"}, headers=admin).status_code == 422


def test_pagination_defaults_and_bounds(client, admin, create_facility) -> None:
    for index in range(3):
        create_facility(code=f"PAGE-{index}", name=f"Page Facility {index}")
    body = client.get(BASE, headers=admin).json()
    assert (body["limit"], body["offset"], body["total"]) == (20, 0, 3)

    page = client.get(BASE, params={"limit": 2, "offset": 2}, headers=admin).json()
    assert len(page["items"]) == 1 and page["total"] == 3
    assert client.get(BASE, params={"limit": 100}, headers=admin).status_code == 200
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "abc"}):
        response = client.get(BASE, params=params, headers=admin)
        assert response.status_code == 422, params
        assert _error_code(response) == "validation_error"


def test_update_facility_including_timezone(client, admin, create_facility) -> None:
    facility = create_facility()
    response = client.patch(
        f"{BASE}/{facility['id']}",
        json={"name": "Northwind Medical Campus", "timezone": "America/New_York", "address_line2": None},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Northwind Medical Campus"
    assert body["timezone"] == "America/New_York"
    assert body["address_line2"] is None
    assert body["code"] == facility["code"]
    assert body["updated_at"] >= facility["updated_at"]
    detail = client.get(f"{BASE}/{facility['id']}", headers=admin).json()
    assert detail["utc_offset"] in {"-05:00", "-04:00"}


@pytest.mark.parametrize(
    "body",
    [{"timezone": "Not/AZone"}, {"code": "NEW"}, {"is_active": False}, {"name": None}, {"timezone": None}],
    ids=["bad-timezone", "code-immutable", "is-active", "null-name", "null-timezone"],
)
def test_invalid_facility_update_is_422(client, admin, create_facility, body) -> None:
    facility = create_facility()
    response = client.patch(f"{BASE}/{facility['id']}", json=body, headers=admin)
    assert response.status_code == 422
    assert _error_code(response) == "validation_error"


def test_update_missing_facility_is_404(client, admin) -> None:
    response = client.patch(f"{BASE}/{uuid.uuid4()}", json={"name": "Nowhere"}, headers=admin)
    assert response.status_code == 404


def test_deactivate_and_activate_facility(client, admin, create_facility) -> None:
    facility = create_facility()
    deactivated = client.post(f"{BASE}/{facility['id']}/deactivate", headers=admin)
    assert deactivated.status_code == 200 and deactivated.json()["is_active"] is False
    again = client.post(f"{BASE}/{facility['id']}/deactivate", headers=admin)
    assert again.status_code == 200 and again.json()["is_active"] is False
    # Never hard-deleted: still retrievable while inactive.
    assert client.get(f"{BASE}/{facility['id']}", headers=admin).json()["is_active"] is False
    activated = client.post(f"{BASE}/{facility['id']}/activate", headers=admin)
    assert activated.status_code == 200 and activated.json()["is_active"] is True


@pytest.mark.parametrize("action", ["activate", "deactivate"])
def test_status_change_on_missing_facility_is_404(client, admin, action) -> None:
    response = client.post(f"{BASE}/{uuid.uuid4()}/{action}", headers=admin)
    assert response.status_code == 404
    assert _error_code(response) == "not_found"


def test_no_delete_endpoint(client, admin, create_facility) -> None:
    facility = create_facility()
    assert client.delete(f"{BASE}/{facility['id']}", headers=admin).status_code == 405
