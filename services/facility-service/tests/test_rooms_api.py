import uuid

import pytest

DEPARTMENTS = "/api/v1/departments"


def test_create_room(client, admin, department) -> None:
    response = client.post(
        f"{DEPARTMENTS}/{department['id']}/rooms",
        json={"room_number": "3a-12", "room_type": "WARD"},
        headers=admin,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["room_number"], body["room_type"], body["is_active"]) == ("3A-12", "WARD", True)
    assert body["department_id"] == department["id"]


def test_duplicate_room_number_within_department_is_409(client, admin, department, create_room) -> None:
    create_room(department["id"], room_number="101")
    response = client.post(
        f"{DEPARTMENTS}/{department['id']}/rooms",
        json={"room_number": "101", "room_type": "OTHER"},
        headers=admin,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_same_room_number_in_other_department_is_allowed(department, create_department, create_room) -> None:
    other = create_department(department["facility_id"], code="ER")
    create_room(department["id"], room_number="101")
    assert create_room(other["id"], room_number="101")["department_id"] == other["id"]


def test_room_in_missing_department_is_404(client, admin) -> None:
    response = client.post(
        f"{DEPARTMENTS}/{uuid.uuid4()}/rooms", json={"room_number": "1", "room_type": "WARD"}, headers=admin
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_room_in_inactive_department_is_409(client, admin, department) -> None:
    client.patch(f"{DEPARTMENTS}/{department['id']}", json={"is_active": False}, headers=admin)
    response = client.post(
        f"{DEPARTMENTS}/{department['id']}/rooms",
        json={"room_number": "1", "room_type": "WARD"},
        headers=admin,
    )
    assert response.status_code == 409


def test_room_in_department_of_inactive_facility_is_409(client, admin, department) -> None:
    client.post(f"/api/v1/facilities/{department['facility_id']}/deactivate", headers=admin)
    response = client.post(
        f"{DEPARTMENTS}/{department['id']}/rooms",
        json={"room_number": "1", "room_type": "WARD"},
        headers=admin,
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"room_number": "1", "room_type": "KITCHEN"},
        {"room_number": "", "room_type": "WARD"},
        {"room_number": "1 2", "room_type": "WARD"},
        {"room_type": "WARD"},
        {"room_number": "1", "room_type": "WARD", "is_active": False},
    ],
    ids=["bad-type", "empty-number", "space-in-number", "missing-number", "extra-field"],
)
def test_invalid_room_payload_is_422(client, admin, department, body) -> None:
    assert client.post(f"{DEPARTMENTS}/{department['id']}/rooms", json=body, headers=admin).status_code == 422


def test_list_rooms(client, admin, department, create_room) -> None:
    for number, room_type in (("B2", "WARD"), ("A1", "CONSULTATION"), ("C3", "PROCEDURE")):
        create_room(department["id"], room_number=number, room_type=room_type)
    url = f"{DEPARTMENTS}/{department['id']}/rooms"
    body = client.get(url, headers=admin).json()
    assert [item["room_number"] for item in body["items"]] == ["A1", "B2", "C3"]
    assert (body["total"], body["limit"], body["offset"]) == (3, 20, 0)
    page = client.get(url, params={"limit": 1, "offset": 2}, headers=admin).json()
    assert [item["room_number"] for item in page["items"]] == ["C3"]
    assert client.get(url, params={"active": "false"}, headers=admin).json()["total"] == 0
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        assert client.get(url, params=params, headers=admin).status_code == 422


def test_list_rooms_of_missing_department_is_404(client, admin) -> None:
    assert client.get(f"{DEPARTMENTS}/{uuid.uuid4()}/rooms", headers=admin).status_code == 404
