import logging

import pytest
from fastapi.testclient import TestClient

from app.domain.roles import Role


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_readiness_checks_database(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_request_id_is_propagated(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"


def test_openapi_documents_endpoints_and_bearer_auth(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert {
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/users",
        "/api/v1/users/{user_id}",
        "/api/v1/roles",
    } <= set(schema["paths"])
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_roles_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/roles").status_code == 401


@pytest.mark.parametrize("role", list(Role))
def test_any_authenticated_role_can_list_roles(client: TestClient, auth_headers, role: Role) -> None:
    response = client.get("/api/v1/roles", headers=auth_headers(role))
    assert response.status_code == 200
    roles = {item["name"]: item for item in response.json()}
    assert set(roles) == {"ADMIN", "RECEPTIONIST", "DOCTOR", "READ_ONLY"}
    assert "users:manage" in roles["ADMIN"]["permissions"]
    assert roles["READ_ONLY"]["permissions"] == ["roles:read"]


def test_unhandled_error_keeps_request_id_and_is_logged(app, client: TestClient, caplog) -> None:
    def boom() -> None:
        raise RuntimeError("synthetic failure with secret-detail")

    app.add_api_route("/boom", boom)
    caplog.set_level(logging.INFO)

    response = client.get("/boom", headers={"X-Request-ID": "trace-500"})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "trace-500"
    assert response.json() == {"error": {"code": "internal_error", "message": "Internal server error"}}
    assert "secret-detail" not in response.text
    records = {getattr(r, "event", None): r for r in caplog.records}
    assert records["unhandled_error"].request_id == "trace-500"
    assert records["http_request"].status_code == 500
    assert records["http_request"].request_id == "trace-500"
