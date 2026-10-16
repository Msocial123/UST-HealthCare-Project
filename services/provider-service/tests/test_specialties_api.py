import uuid

import pytest

URL = "/api/v1/specialties"


def test_create_specialty_normalizes_code(client, admin) -> None:
    response = client.post(
        URL,
        json={"code": " cardiology ", "name": "Cardiology", "description": "Heart care unit"},
        headers=admin,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "CARDIOLOGY"
    assert body["name"] == "Cardiology"
    assert body["is_active"] is True
    uuid.UUID(body["id"])
    assert body["created_at"].endswith(("Z", "+00:00"))


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "No Code"},
        {"code": "X", "name": "Too short code"},
        {"code": "BAD CODE", "name": "Space in code"},
        {"code": "C" * 33, "name": "Too long code"},
        {"code": "OK", "name": ""},
        {"code": "OK", "name": "Fine", "unexpected": True},
        {"code": "OK", "name": "Fine", "is_active": "maybe"},
    ],
)
def test_create_specialty_invalid_payload_is_422(client, admin, payload) -> None:
    response = client.post(URL, json=payload, headers=admin)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_duplicate_specialty_code_is_409(client, admin, create_specialty) -> None:
    create_specialty("CARDIOLOGY", "Cardiology")
    response = client.post(URL, json={"code": "cardiology", "name": "Heart Medicine"}, headers=admin)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_duplicate_specialty_name_is_409(client, admin, create_specialty) -> None:
    create_specialty("CARDIOLOGY", "Cardiology")
    response = client.post(URL, json={"code": "CARDIO2", "name": "cardiology"}, headers=admin)
    assert response.status_code == 409


def test_list_specialties_filters_and_paginates(client, auth, create_specialty) -> None:
    for code in ("ALPHA", "BRAVO", "CHARLIE"):
        create_specialty(code)
    create_specialty("DELTA", is_active=False)
    headers = auth("READ_ONLY")

    page = client.get(URL, params={"limit": 2, "offset": 0}, headers=headers).json()
    assert page["total"] == 4
    assert [item["code"] for item in page["items"]] == ["ALPHA", "BRAVO"]
    assert page["limit"] == 2 and page["offset"] == 0

    second = client.get(URL, params={"limit": 2, "offset": 2}, headers=headers).json()
    assert [item["code"] for item in second["items"]] == ["CHARLIE", "DELTA"]

    active = client.get(URL, params={"active": "true"}, headers=headers).json()
    assert active["total"] == 3
    inactive = client.get(URL, params={"active": "false"}, headers=headers).json()
    assert [item["code"] for item in inactive["items"]] == ["DELTA"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "abc"}])
def test_list_specialties_pagination_bounds(client, admin, params) -> None:
    assert client.get(URL, params=params, headers=admin).status_code == 422


def test_list_specialties_default_limit(client, admin) -> None:
    assert client.get(URL, headers=admin).json()["limit"] == 20


def test_update_and_deactivate_specialty(client, admin, create_specialty) -> None:
    specialty = create_specialty("DERMATOLOGY", "Dermatology")
    response = client.patch(
        f"{URL}/{specialty['id']}",
        json={"name": "Dermatology & Skin", "description": "Updated", "is_active": False},
        headers=admin,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Dermatology & Skin"
    assert body["is_active"] is False
    assert body["code"] == "DERMATOLOGY"
    assert body["updated_at"] >= specialty["updated_at"]


def test_update_specialty_code_is_not_allowed(client, admin, create_specialty) -> None:
    specialty = create_specialty("ONCOLOGY")
    assert client.patch(f"{URL}/{specialty['id']}", json={"code": "ONC"}, headers=admin).status_code == 422


def test_update_specialty_null_name_is_422(client, admin, create_specialty) -> None:
    specialty = create_specialty("ONCOLOGY")
    assert client.patch(f"{URL}/{specialty['id']}", json={"name": None}, headers=admin).status_code == 422


def test_update_specialty_duplicate_name_is_409(client, admin, create_specialty) -> None:
    create_specialty("ONCOLOGY", "Oncology")
    other = create_specialty("UROLOGY", "Urology")
    assert client.patch(f"{URL}/{other['id']}", json={"name": "Oncology"}, headers=admin).status_code == 409


def test_update_missing_specialty_is_404(client, admin) -> None:
    response = client.patch(f"{URL}/{uuid.uuid4()}", json={"name": "Ghost"}, headers=admin)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_update_specialty_invalid_id_is_422(client, admin) -> None:
    assert client.patch(f"{URL}/not-a-uuid", json={"name": "Ghost"}, headers=admin).status_code == 422
