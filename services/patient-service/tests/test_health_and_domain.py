import re

from fastapi.testclient import TestClient

from app.domain.patients import MRN_LENGTH, generate_mrn
from app.domain.roles import Permission, Role, permissions_for


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_readiness_checks_database(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_openapi_docs_are_enabled(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert {"/health", "/api/v1/patients", "/api/v1/patients/{patient_id}"} <= set(schema["paths"])
    assert "/api/v1/patients/{patient_id}/deactivate" in schema["paths"]
    assert client.get("/docs").status_code == 200


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_generated_mrns_are_well_formed_and_distinct() -> None:
    mrns = {generate_mrn() for _ in range(500)}
    assert len(mrns) == 500
    for mrn in mrns:
        assert len(mrn) == MRN_LENGTH
        assert re.fullmatch(r"MRN-[0-9A-HJKMNP-TV-Z]{10}", mrn)


def test_role_permission_map() -> None:
    assert permissions_for([Role.ADMIN]) == frozenset(Permission)
    assert permissions_for([Role.RECEPTIONIST]) == {Permission.PATIENTS_READ, Permission.PATIENTS_WRITE}
    assert permissions_for([Role.DOCTOR]) == {Permission.PATIENTS_READ}
    assert permissions_for([Role.READ_ONLY]) == frozenset()
    assert permissions_for([Role.DOCTOR, Role.RECEPTIONIST]) == {
        Permission.PATIENTS_READ,
        Permission.PATIENTS_WRITE,
    }
