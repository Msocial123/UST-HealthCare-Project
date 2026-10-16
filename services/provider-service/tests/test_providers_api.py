import uuid

import pytest

from tests.conftest import provider_payload

URL = "/api/v1/providers"


@pytest.fixture
def specialties(create_specialty) -> dict[str, str]:
    return {code: create_specialty(code)["id"] for code in ("CARDIOLOGY", "NEUROLOGY", "PEDIATRICS")}


def test_create_provider_with_specialties(client, admin, specialties) -> None:
    facility_id, department_id = str(uuid.uuid4()), str(uuid.uuid4())
    payload = provider_payload(
        [specialties["CARDIOLOGY"], specialties["NEUROLOGY"]],
        primary=specialties["NEUROLOGY"],
        license_number="lic-demo-0001",
        facility_id=facility_id,
        department_id=department_id,
    )
    response = client.post(URL, json=payload, headers=admin)
    assert response.status_code == 201
    body = response.json()
    assert body["provider_number"].startswith("PRV-") and len(body["provider_number"]) == 12
    assert body["license_number"] == "LIC-DEMO-0001"
    assert body["is_active"] is True
    assert body["facility_id"] == facility_id and body["department_id"] == department_id
    assert [(s["code"], s["is_primary"]) for s in body["specialties"]] == [
        ("NEUROLOGY", True),
        ("CARDIOLOGY", False),
    ]


def test_provider_number_is_server_generated(client, admin, specialties) -> None:
    payload = provider_payload([specialties["CARDIOLOGY"]], provider_number="PRV-HACKED01")
    assert client.post(URL, json=payload, headers=admin).status_code == 422
    first = client.post(URL, json=provider_payload([specialties["CARDIOLOGY"]]), headers=admin).json()
    second = client.post(URL, json=provider_payload([specialties["CARDIOLOGY"]]), headers=admin).json()
    assert first["provider_number"] != second["provider_number"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"work_email": "not-an-email"},
        {"work_phone": "call me"},
        {"years_of_experience": -1},
        {"years_of_experience": 71},
        {"first_name": ""},
        {"license_number": "a b"},
        {"specialties": []},
        {"facility_id": "not-a-uuid"},
        {"is_active": False},
    ],
)
def test_create_provider_invalid_payload_is_422(client, admin, specialties, overrides) -> None:
    response = client.post(
        URL, json=provider_payload([specialties["CARDIOLOGY"]], **overrides), headers=admin
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_validation_errors_do_not_echo_contact_details(client, admin, specialties) -> None:
    payload = provider_payload([specialties["CARDIOLOGY"]], work_email="synthetic.secret@@provider.example")
    response = client.post(URL, json=payload, headers=admin)
    assert response.status_code == 422
    assert "synthetic.secret" not in response.text


@pytest.mark.parametrize("primary_flags", [(False, False), (True, True)], ids=["no-primary", "two-primaries"])
def test_provider_requires_exactly_one_primary(client, admin, specialties, primary_flags) -> None:
    payload = provider_payload([specialties["CARDIOLOGY"], specialties["NEUROLOGY"]])
    for item, flag in zip(payload["specialties"], primary_flags, strict=True):
        item["is_primary"] = flag
    response = client.post(URL, json=payload, headers=admin)
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Exactly one specialty must be marked as primary"


def test_duplicate_specialty_assignment_is_422(client, admin, specialties) -> None:
    sid = specialties["CARDIOLOGY"]
    payload = provider_payload([sid])
    payload["specialties"].append({"specialty_id": sid, "is_primary": False})
    assert client.post(URL, json=payload, headers=admin).status_code == 422


def test_unknown_specialty_is_404(client, admin, specialties) -> None:
    missing = str(uuid.uuid4())
    response = client.post(URL, json=provider_payload([specialties["CARDIOLOGY"], missing]), headers=admin)
    assert response.status_code == 404
    assert response.json()["error"]["details"] == {"specialty_ids": [missing]}


def test_inactive_specialty_assignment_is_409(client, admin, create_specialty) -> None:
    inactive = create_specialty("RETIRED", is_active=False)["id"]
    response = client.post(URL, json=provider_payload([inactive]), headers=admin)
    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"specialty_ids": [inactive]}


def test_duplicate_license_number_is_409(client, admin, specialties, create_provider) -> None:
    create_provider([specialties["CARDIOLOGY"]], license_number="LIC-DUP-1")
    response = client.post(
        URL, json=provider_payload([specialties["CARDIOLOGY"]], license_number="lic-dup-1"), headers=admin
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.parametrize("role", ["ADMIN", "RECEPTIONIST", "DOCTOR"])
def test_get_provider(client, auth, specialties, create_provider, role) -> None:
    provider = create_provider([specialties["PEDIATRICS"]])
    response = client.get(f"{URL}/{provider['id']}", headers=auth(role))
    assert response.status_code == 200
    assert response.json() == provider


def test_get_missing_provider_is_404(client, admin) -> None:
    response = client.get(f"{URL}/{uuid.uuid4()}", headers=admin)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_get_provider_invalid_id_is_422(client, admin) -> None:
    assert client.get(f"{URL}/not-a-uuid", headers=admin).status_code == 422


@pytest.fixture
def directory(specialties, create_provider) -> dict[str, dict]:
    return {
        "avery": create_provider([specialties["CARDIOLOGY"]], first_name="Avery", last_name="Stone"),
        "blake": create_provider(
            [specialties["NEUROLOGY"], specialties["CARDIOLOGY"]],
            primary=specialties["NEUROLOGY"],
            first_name="Blake",
            last_name="Rivers",
        ),
        "casey": create_provider([specialties["PEDIATRICS"]], first_name="Casey", last_name="Moss"),
    }


def _names(response) -> list[str]:
    return [item["first_name"] for item in response.json()["items"]]


def test_search_by_name(client, auth, directory) -> None:
    headers = auth("RECEPTIONIST")
    assert _names(client.get(URL, params={"search": "rive"}, headers=headers)) == ["Blake"]
    assert _names(client.get(URL, params={"search": "Casey Moss"}, headers=headers)) == ["Casey"]
    assert _names(client.get(URL, params={"search": "%"}, headers=headers)) == []


def test_search_by_provider_number(client, auth, directory) -> None:
    number = directory["casey"]["provider_number"]
    response = client.get(URL, params={"search": number.lower()}, headers=auth("DOCTOR"))
    assert _names(response) == ["Casey"]


def test_search_by_specialty_code(client, admin, directory) -> None:
    assert _names(client.get(URL, params={"search": "cardiology"}, headers=admin)) == ["Blake", "Avery"]


def test_filter_by_specialty(client, admin, directory) -> None:
    response = client.get(URL, params={"specialty": "neurology"}, headers=admin)
    assert response.json()["total"] == 1
    assert _names(response) == ["Blake"]
    assert client.get(URL, params={"specialty": "UNKNOWN"}, headers=admin).json()["total"] == 0


def test_filter_by_active_and_paginate(client, admin, directory) -> None:
    client.post(f"{URL}/{directory['avery']['id']}/deactivate", headers=admin)
    active = client.get(URL, params={"active": "true"}, headers=admin)
    assert _names(active) == ["Casey", "Blake"]
    assert _names(client.get(URL, params={"active": "false"}, headers=admin)) == ["Avery"]

    page = client.get(URL, params={"limit": 1, "offset": 1}, headers=admin).json()
    assert page["total"] == 3 and page["limit"] == 1 and page["offset"] == 1
    assert [item["first_name"] for item in page["items"]] == ["Blake"]
    assert client.get(URL, headers=admin).json()["limit"] == 20


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"search": ""},
        {"specialty": "bad code"},
        {"active": "x"},
    ],
)
def test_search_invalid_params_are_422(client, admin, params) -> None:
    assert client.get(URL, params=params, headers=admin).status_code == 422


def test_limit_upper_bound_is_accepted(client, admin) -> None:
    assert client.get(URL, params={"limit": 100}, headers=admin).status_code == 200


def test_update_provider_profile(client, admin, specialties, create_provider) -> None:
    provider = create_provider([specialties["CARDIOLOGY"]])
    response = client.patch(
        f"{URL}/{provider['id']}",
        json={"title": "Prof", "years_of_experience": 12, "work_phone": "+1 555 0199", "facility_id": None},
        headers=admin,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Prof" and body["years_of_experience"] == 12
    assert body["provider_number"] == provider["provider_number"]
    assert body["updated_at"] >= provider["updated_at"]


def test_update_provider_specialties_replaces_set(client, admin, specialties, create_provider) -> None:
    provider = create_provider(
        [specialties["CARDIOLOGY"], specialties["NEUROLOGY"]], primary=specialties["CARDIOLOGY"]
    )
    new_set = [
        {"specialty_id": specialties["NEUROLOGY"], "is_primary": True},
        {"specialty_id": specialties["PEDIATRICS"], "is_primary": False},
    ]
    response = client.patch(f"{URL}/{provider['id']}", json={"specialties": new_set}, headers=admin)
    assert response.status_code == 200
    assert [(s["code"], s["is_primary"]) for s in response.json()["specialties"]] == [
        ("NEUROLOGY", True),
        ("PEDIATRICS", False),
    ]
    fetched = client.get(f"{URL}/{provider['id']}", headers=admin).json()
    assert {s["code"] for s in fetched["specialties"]} == {"NEUROLOGY", "PEDIATRICS"}


def test_update_provider_swap_primary(client, admin, specialties, create_provider) -> None:
    provider = create_provider(
        [specialties["CARDIOLOGY"], specialties["NEUROLOGY"]], primary=specialties["CARDIOLOGY"]
    )
    swapped = [
        {"specialty_id": specialties["CARDIOLOGY"], "is_primary": False},
        {"specialty_id": specialties["NEUROLOGY"], "is_primary": True},
    ]
    response = client.patch(f"{URL}/{provider['id']}", json={"specialties": swapped}, headers=admin)
    assert response.status_code == 200
    primary = [s["code"] for s in response.json()["specialties"] if s["is_primary"]]
    assert primary == ["NEUROLOGY"]


def test_update_provider_without_primary_is_422(client, admin, specialties, create_provider) -> None:
    provider = create_provider([specialties["CARDIOLOGY"]])
    body = {"specialties": [{"specialty_id": specialties["CARDIOLOGY"], "is_primary": False}]}
    assert client.patch(f"{URL}/{provider['id']}", json=body, headers=admin).status_code == 422


def test_update_provider_inactive_specialty_rules(client, admin, specialties, create_provider) -> None:
    provider = create_provider([specialties["CARDIOLOGY"]])
    client.patch(f"/api/v1/specialties/{specialties['CARDIOLOGY']}", json={"is_active": False}, headers=admin)
    client.patch(f"/api/v1/specialties/{specialties['NEUROLOGY']}", json={"is_active": False}, headers=admin)

    keep_existing = [
        {"specialty_id": specialties["CARDIOLOGY"], "is_primary": True},
        {"specialty_id": specialties["PEDIATRICS"], "is_primary": False},
    ]
    response = client.patch(f"{URL}/{provider['id']}", json={"specialties": keep_existing}, headers=admin)
    assert response.status_code == 200
    cardiology = next(s for s in response.json()["specialties"] if s["code"] == "CARDIOLOGY")
    assert cardiology["is_active"] is False

    add_inactive = [*keep_existing, {"specialty_id": specialties["NEUROLOGY"], "is_primary": False}]
    response = client.patch(f"{URL}/{provider['id']}", json={"specialties": add_inactive}, headers=admin)
    assert response.status_code == 409


@pytest.mark.parametrize(
    "body", [{"first_name": None}, {"specialties": None}, {"is_active": False}, {"x": 1}]
)
def test_update_provider_invalid_payload_is_422(client, admin, specialties, create_provider, body) -> None:
    provider = create_provider([specialties["CARDIOLOGY"]])
    assert client.patch(f"{URL}/{provider['id']}", json=body, headers=admin).status_code == 422


def test_update_provider_duplicate_license_is_409(client, admin, specialties, create_provider) -> None:
    create_provider([specialties["CARDIOLOGY"]], license_number="LIC-TAKEN")
    other = create_provider([specialties["CARDIOLOGY"]])
    response = client.patch(f"{URL}/{other['id']}", json={"license_number": "lic-taken"}, headers=admin)
    assert response.status_code == 409


def test_update_provider_same_license_is_allowed(client, admin, specialties, create_provider) -> None:
    provider = create_provider([specialties["CARDIOLOGY"]], license_number="LIC-OWN")
    response = client.patch(f"{URL}/{provider['id']}", json={"license_number": "LIC-OWN"}, headers=admin)
    assert response.status_code == 200


def test_update_missing_provider_is_404(client, admin) -> None:
    assert client.patch(f"{URL}/{uuid.uuid4()}", json={"title": "Dr"}, headers=admin).status_code == 404


def test_deactivate_and_activate_provider(client, admin, auth, specialties, create_provider) -> None:
    provider = create_provider([specialties["CARDIOLOGY"]])
    deactivated = client.post(f"{URL}/{provider['id']}/deactivate", headers=admin)
    assert deactivated.status_code == 200 and deactivated.json()["is_active"] is False
    assert client.post(f"{URL}/{provider['id']}/deactivate", headers=admin).json()["is_active"] is False

    still_there = client.get(f"{URL}/{provider['id']}", headers=auth("RECEPTIONIST"))
    assert still_there.status_code == 200 and still_there.json()["is_active"] is False

    activated = client.post(f"{URL}/{provider['id']}/activate", headers=admin)
    assert activated.status_code == 200 and activated.json()["is_active"] is True


@pytest.mark.parametrize("action", ["activate", "deactivate"])
def test_status_change_missing_provider_is_404(client, admin, action) -> None:
    assert client.post(f"{URL}/{uuid.uuid4()}/{action}", headers=admin).status_code == 404


def test_no_delete_endpoint(client, admin, specialties, create_provider) -> None:
    provider = create_provider([specialties["CARDIOLOGY"]])
    assert client.delete(f"{URL}/{provider['id']}", headers=admin).status_code == 405
