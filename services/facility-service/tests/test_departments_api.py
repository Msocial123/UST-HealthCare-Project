import uuid

import pytest

FACILITIES = "/api/v1/facilities"
DEPARTMENTS = "/api/v1/departments"


def test_create_department(client, admin, create_facility) -> None:
    facility = create_facility()
    response = client.post(
        f"{FACILITIES}/{facility['id']}/departments",
        json={"code": "cardio", "name": "Cardiology", "floor": "3", "phone_extension": "2101"},
        headers=admin,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["code"] == "CARDIO"
    assert body["facility_id"] == facility["id"]
    assert (body["floor"], body["phone_extension"], body["is_active"]) == ("3", "2101", True)


def test_duplicate_department_code_within_facility_is_409(client, admin, create_facility, create_department):
    facility = create_facility()
    create_department(facility["id"], code="CARDIO")
    response = client.post(
        f"{FACILITIES}/{facility['id']}/departments", json={"code": "Cardio", "name": "Again"}, headers=admin
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_same_department_code_in_other_facility_is_allowed(create_facility, create_department) -> None:
    first, second = create_facility(), create_facility()
    create_department(first["id"], code="CARDIO")
    assert create_department(second["id"], code="CARDIO")["facility_id"] == second["id"]


def test_department_under_inactive_facility_is_409(client, admin, create_facility) -> None:
    facility = create_facility()
    client.post(f"{FACILITIES}/{facility['id']}/deactivate", headers=admin)
    response = client.post(
        f"{FACILITIES}/{facility['id']}/departments", json={"code": "ER", "name": "Emergency"}, headers=admin
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_department_under_missing_facility_is_404(client, admin) -> None:
    response = client.post(
        f"{FACILITIES}/{uuid.uuid4()}/departments", json={"code": "ER", "name": "Emergency"}, headers=admin
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    "body",
    [
        {"code": "E", "name": "Emergency"},
        {"code": "ER", "name": "Emergency", "phone_extension": "ext-1"},
        {"code": "ER", "name": "Emergency", "floor": "3rd!"},
        {"name": "Emergency"},
        {"code": "ER", "name": "Emergency", "facility_id": str(uuid.uuid4())},
    ],
    ids=["short-code", "bad-extension", "bad-floor", "missing-code", "extra-field"],
)
def test_invalid_department_payload_is_422(client, admin, create_facility, body) -> None:
    facility = create_facility()
    response = client.post(f"{FACILITIES}/{facility['id']}/departments", json=body, headers=admin)
    assert response.status_code == 422


def test_list_departments_with_filters_and_pagination(
    client, admin, create_facility, create_department
) -> None:
    facility = create_facility()
    other = create_facility()
    codes = ["ER", "CARDIO", "RADIO"]
    created = {code: create_department(facility["id"], code=code) for code in codes}
    create_department(other["id"], code="ONCO")
    client.patch(f"{DEPARTMENTS}/{created['RADIO']['id']}", json={"is_active": False}, headers=admin)

    url = f"{FACILITIES}/{facility['id']}/departments"
    body = client.get(url, headers=admin).json()
    assert [item["code"] for item in body["items"]] == ["CARDIO", "ER", "RADIO"]
    assert (body["total"], body["limit"], body["offset"]) == (3, 20, 0)
    assert [
        i["code"] for i in client.get(url, params={"active": "false"}, headers=admin).json()["items"]
    ] == ["RADIO"]
    page = client.get(url, params={"limit": 1, "offset": 1}, headers=admin).json()
    assert [item["code"] for item in page["items"]] == ["ER"]
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        assert client.get(url, params=params, headers=admin).status_code == 422


def test_list_departments_of_missing_facility_is_404(client, admin) -> None:
    assert client.get(f"{FACILITIES}/{uuid.uuid4()}/departments", headers=admin).status_code == 404


def test_get_department(client, admin, department) -> None:
    response = client.get(f"{DEPARTMENTS}/{department['id']}", headers=admin)
    assert response.status_code == 200
    assert response.json() == department


def test_get_missing_department_is_404(client, admin) -> None:
    response = client.get(f"{DEPARTMENTS}/{uuid.uuid4()}", headers=admin)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_update_and_deactivate_department(client, admin, department) -> None:
    url = f"{DEPARTMENTS}/{department['id']}"
    response = client.patch(url, json={"name": "Cardiac Sciences", "floor": None}, headers=admin)
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Cardiac Sciences" and response.json()["floor"] is None

    deactivated = client.patch(url, json={"is_active": False}, headers=admin)
    assert deactivated.status_code == 200 and deactivated.json()["is_active"] is False
    reactivated = client.patch(url, json={"is_active": True}, headers=admin)
    assert reactivated.status_code == 200 and reactivated.json()["is_active"] is True


def test_cannot_reactivate_department_of_inactive_facility(client, admin, department) -> None:
    url = f"{DEPARTMENTS}/{department['id']}"
    client.patch(url, json={"is_active": False}, headers=admin)
    client.post(f"{FACILITIES}/{department['facility_id']}/deactivate", headers=admin)
    response = client.patch(url, json={"is_active": True}, headers=admin)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_deactivating_facility_does_not_cascade(client, admin, department) -> None:
    client.post(f"{FACILITIES}/{department['facility_id']}/deactivate", headers=admin)
    assert client.get(f"{DEPARTMENTS}/{department['id']}", headers=admin).json()["is_active"] is True


@pytest.mark.parametrize(
    "body",
    [{"code": "NEW"}, {"name": None}, {"is_active": None}, {"facility_id": str(uuid.uuid4())}],
    ids=["code-immutable", "null-name", "null-active", "move-facility"],
)
def test_invalid_department_update_is_422(client, admin, department, body) -> None:
    assert client.patch(f"{DEPARTMENTS}/{department['id']}", json=body, headers=admin).status_code == 422


def test_update_missing_department_is_404(client, admin) -> None:
    response = client.patch(f"{DEPARTMENTS}/{uuid.uuid4()}", json={"name": "Nothing"}, headers=admin)
    assert response.status_code == 404
