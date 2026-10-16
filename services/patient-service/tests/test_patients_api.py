import re
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.time import utcnow
from app.domain.patients import Sex
from app.domain.roles import Role
from app.models.patient import Patient
from app.services import patient_service

PATIENTS_URL = "/api/v1/patients"
SUMMARY_FIELDS = {
    "id",
    "medical_record_number",
    "first_name",
    "last_name",
    "date_of_birth",
    "sex",
    "is_active",
}


def _payload(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "first_name": "  Jordan ",
        "last_name": "Fictional",
        "date_of_birth": "1978-11-30",
        "sex": "MALE",
        "phone": "+1 555 0100",
        "email": "Jordan.Fictional@Example.COM",
        "address_line1": "1 Synthetic Way",
        "city": "Testville",
        "state": "TS",
        "postal_code": "00000",
        "country": "us",
    }
    payload.update(overrides)
    return {key: value for key, value in payload.items() if value is not ...}


# --- create ------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.RECEPTIONIST, Role.ADMIN])
def test_register_patient(client: TestClient, auth_headers, db_session, role: Role) -> None:
    response = client.post(PATIENTS_URL, json=_payload(), headers=auth_headers(role))

    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(r"MRN-[0-9A-HJKMNP-TV-Z]{10}", body["medical_record_number"])
    assert body["first_name"] == "Jordan"
    assert body["email"] == "jordan.fictional@example.com"
    assert body["country"] == "US"
    assert body["date_of_birth"] == "1978-11-30"
    assert body["sex"] == "MALE"
    assert body["is_active"] is True
    assert body["address_line2"] is None
    assert body["created_at"].endswith(("Z", "+00:00"))
    assert db_session.get(Patient, uuid.UUID(body["id"])) is not None


def test_register_with_only_required_fields(client: TestClient, auth_headers) -> None:
    body = {"first_name": "Sam", "last_name": "Minimal", "date_of_birth": "2001-01-01", "sex": "UNKNOWN"}
    response = client.post(PATIENTS_URL, json=body, headers=auth_headers())
    assert response.status_code == 201
    assert response.json()["phone"] is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"first_name": ...},
        {"last_name": "   "},
        {"first_name": "x" * 101},
        {"date_of_birth": ...},
        {"date_of_birth": "not-a-date"},
        {"date_of_birth": (utcnow().date() + timedelta(days=1)).isoformat()},
        {"date_of_birth": "1899-12-31"},
        {"sex": "M"},
        {"sex": ...},
        {"email": "not-an-email"},
        {"phone": "call me maybe"},
        {"phone": "12"},
        {"country": "USA"},
        {"postal_code": "<script>"},
        {"medical_record_number": "MRN-CLIENTSET1"},
        {"is_active": False},
        {"id": str(uuid.uuid4())},
    ],
)
def test_register_rejects_invalid_payloads(client: TestClient, auth_headers, overrides: dict) -> None:
    response = client.post(PATIENTS_URL, json=_payload(**overrides), headers=auth_headers())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_validation_errors_never_echo_submitted_values(client: TestClient, auth_headers) -> None:
    response = client.post(
        PATIENTS_URL,
        json=_payload(email="secret.person@@example.com", date_of_birth="2999-01-01"),
        headers=auth_headers(),
    )
    assert response.status_code == 422
    assert "secret.person" not in response.text
    assert "2999" not in response.text


def test_mrn_collision_is_retried(client: TestClient, auth_headers, make_patient, monkeypatch) -> None:
    existing = make_patient()
    generated = iter([existing.medical_record_number, "MRN-0000000001"])
    monkeypatch.setattr(patient_service.patient_domain, "generate_mrn", lambda: next(generated))

    response = client.post(PATIENTS_URL, json=_payload(), headers=auth_headers())
    assert response.status_code == 201
    assert response.json()["medical_record_number"] == "MRN-0000000001"


def test_duplicate_mrn_is_409_when_retries_are_exhausted(
    client: TestClient, auth_headers, make_patient, db_session, monkeypatch
) -> None:
    existing = make_patient()
    monkeypatch.setattr(
        patient_service.patient_domain, "generate_mrn", lambda: existing.medical_record_number
    )

    response = client.post(PATIENTS_URL, json=_payload(), headers=auth_headers())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert db_session.scalar(select(func.count()).select_from(Patient)) == 1


# --- get ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.RECEPTIONIST, Role.DOCTOR, Role.ADMIN])
def test_get_patient(client: TestClient, auth_headers, make_patient, role: Role) -> None:
    patient = make_patient(phone="+1 555 0101", city="Testville")
    response = client.get(f"{PATIENTS_URL}/{patient.id}", headers=auth_headers(role))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(patient.id)
    assert body["medical_record_number"] == patient.medical_record_number
    assert body["phone"] == "+1 555 0101"


def test_get_missing_patient_is_404(client: TestClient, auth_headers) -> None:
    response = client.get(f"{PATIENTS_URL}/{uuid.uuid4()}", headers=auth_headers())
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Patient not found"}}


def test_get_with_invalid_id_is_422(client: TestClient, auth_headers) -> None:
    assert client.get(f"{PATIENTS_URL}/not-a-uuid", headers=auth_headers()).status_code == 422


# --- list / search -----------------------------------------------------------------------------


def test_list_is_paginated_and_ordered_by_name(client: TestClient, auth_headers, make_patient) -> None:
    for last_name in ["Charlie", "alpha", "Bravo"]:
        make_patient(last_name=last_name)

    response = client.get(PATIENTS_URL, params={"limit": 2}, headers=auth_headers(Role.DOCTOR))
    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["limit"], body["offset"]) == (3, 2, 0)
    assert [item["last_name"] for item in body["items"]] == ["alpha", "Bravo"]
    assert set(body["items"][0]) == SUMMARY_FIELDS

    second = client.get(PATIENTS_URL, params={"limit": 2, "offset": 2}, headers=auth_headers()).json()
    assert [item["last_name"] for item in second["items"]] == ["Charlie"]


def test_list_default_limit_is_20(client: TestClient, auth_headers, make_patient) -> None:
    for index in range(21):
        make_patient(last_name=f"Pagination{index:02d}")
    body = client.get(PATIENTS_URL, headers=auth_headers()).json()
    assert body["limit"] == 20
    assert len(body["items"]) == 20
    assert body["total"] == 21


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"limit": "abc"}, {"offset": -1}, {"search": ""}, {"search": "x" * 101}],
)
def test_list_rejects_invalid_query(client: TestClient, auth_headers, params: dict) -> None:
    response = client.get(PATIENTS_URL, params=params, headers=auth_headers())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_accepts_limit_bounds(client: TestClient, auth_headers) -> None:
    for limit in (1, 100):
        assert client.get(PATIENTS_URL, params={"limit": limit}, headers=auth_headers()).status_code == 200


@pytest.fixture
def directory(make_patient) -> dict[str, Patient]:
    return {
        "ada": make_patient(first_name="Ada", last_name="Lovelace-Test", date_of_birth=date(1980, 12, 10)),
        "alan": make_patient(first_name="Alan", last_name="Turing-Test", date_of_birth=date(1972, 6, 23)),
        "grace": make_patient(
            first_name="Grace", last_name="Hopper-Test", date_of_birth=date(1980, 12, 10), sex=Sex.FEMALE
        ),
        "inactive": make_patient(first_name="Adele", last_name="Gone-Test", is_active=False),
    }


def _search(client: TestClient, headers: dict, **params: object) -> set[str]:
    response = client.get(PATIENTS_URL, params=params, headers=headers)
    assert response.status_code == 200
    return {item["id"] for item in response.json()["items"]}


def _ids(directory: dict[str, Patient], *names: str) -> set[str]:
    return {str(directory[name].id) for name in names}


def test_search_by_name_prefix_is_case_insensitive(client: TestClient, auth_headers, directory) -> None:
    headers = auth_headers(Role.RECEPTIONIST)
    assert _search(client, headers, search="ad") == _ids(directory, "ada", "inactive")
    assert _search(client, headers, search="TURING") == _ids(directory, "alan")
    assert _search(client, headers, search="ada lovelace") == _ids(directory, "ada")
    assert _search(client, headers, search="ada turing") == set()


def test_search_by_mrn(client: TestClient, auth_headers, directory) -> None:
    mrn = directory["grace"].medical_record_number
    assert _search(client, auth_headers(), search=mrn) == _ids(directory, "grace")
    assert _search(client, auth_headers(), search=mrn.lower()) == _ids(directory, "grace")
    assert _search(client, auth_headers(), search=mrn[:-1]) == set()


def test_search_by_date_of_birth(client: TestClient, auth_headers, directory) -> None:
    assert _search(client, auth_headers(), search="1980-12-10") == _ids(directory, "ada", "grace")
    assert _search(client, auth_headers(), search="1980-12-10 grace") == _ids(directory, "grace")
    assert _search(client, auth_headers(), search="1980-02-31") == set()


def test_search_treats_like_wildcards_literally(client: TestClient, auth_headers, directory) -> None:
    assert _search(client, auth_headers(), search="%") == set()
    assert _search(client, auth_headers(), search="_") == set()


def test_filter_by_active_status(client: TestClient, auth_headers, directory) -> None:
    assert _search(client, auth_headers(), is_active="false") == _ids(directory, "inactive")
    assert _search(client, auth_headers(), search="ad", is_active="true") == _ids(directory, "ada")


# --- update ------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.RECEPTIONIST, Role.ADMIN])
def test_update_demographics(client: TestClient, auth_headers, make_patient, role: Role) -> None:
    patient = make_patient(phone="+1 555 0102", city="Oldtown")
    response = client.patch(
        f"{PATIENTS_URL}/{patient.id}",
        json={"last_name": " Renamed ", "city": None, "sex": "OTHER", "email": "NEW@Example.COM"},
        headers=auth_headers(role),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["last_name"] == "Renamed"
    assert body["city"] is None
    assert body["sex"] == "OTHER"
    assert body["email"] == "new@example.com"
    assert body["phone"] == "+1 555 0102"
    assert body["first_name"] == patient.first_name
    assert body["medical_record_number"] == patient.medical_record_number
    assert body["updated_at"] >= body["created_at"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"first_name": None},
        {"date_of_birth": None},
        {"sex": None},
        {"sex": "X"},
        {"medical_record_number": "MRN-0000000000"},
        {"is_active": True},
        {"unknown_field": "x"},
        {"date_of_birth": "3000-01-01"},
    ],
)
def test_update_rejects_invalid_payloads(client: TestClient, auth_headers, make_patient, body: dict) -> None:
    patient = make_patient()
    response = client.patch(f"{PATIENTS_URL}/{patient.id}", json=body, headers=auth_headers())
    assert response.status_code == 422


def test_update_missing_patient_is_404(client: TestClient, auth_headers) -> None:
    response = client.patch(
        f"{PATIENTS_URL}/{uuid.uuid4()}", json={"city": "X-ville"}, headers=auth_headers()
    )
    assert response.status_code == 404


def test_update_inactive_patient_is_409(client: TestClient, auth_headers, make_patient) -> None:
    patient = make_patient(is_active=False)
    response = client.patch(f"{PATIENTS_URL}/{patient.id}", json={"city": "X-ville"}, headers=auth_headers())
    assert response.status_code == 409
    assert response.json()["error"] == {"code": "conflict", "message": "Inactive patients cannot be updated"}


# --- deactivate --------------------------------------------------------------------------------


def test_deactivate_is_a_soft_delete(client: TestClient, auth_headers, make_patient, db_session) -> None:
    patient = make_patient()
    response = client.post(f"{PATIENTS_URL}/{patient.id}/deactivate", headers=auth_headers(Role.ADMIN))
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    db_session.expire_all()
    stored = db_session.get(Patient, patient.id)
    assert stored is not None and stored.is_active is False
    assert client.get(f"{PATIENTS_URL}/{patient.id}", headers=auth_headers()).json()["is_active"] is False


def test_deactivate_twice_is_409(client: TestClient, auth_headers, make_patient) -> None:
    patient = make_patient()
    url = f"{PATIENTS_URL}/{patient.id}/deactivate"
    assert client.post(url, headers=auth_headers()).status_code == 200
    response = client.post(url, headers=auth_headers())
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Patient is already inactive"


def test_deactivate_missing_patient_is_404(client: TestClient, auth_headers) -> None:
    response = client.post(f"{PATIENTS_URL}/{uuid.uuid4()}/deactivate", headers=auth_headers())
    assert response.status_code == 404


def test_no_hard_delete_endpoint(client: TestClient, auth_headers, make_patient) -> None:
    patient = make_patient()
    assert client.delete(f"{PATIENTS_URL}/{patient.id}", headers=auth_headers()).status_code == 405
