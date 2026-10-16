def test_health_requires_no_auth(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_readiness_checks_database(client) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_openapi_docs_enabled(client) -> None:
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    for path in (
        "/api/v1/facilities",
        "/api/v1/facilities/{facility_id}",
        "/api/v1/facilities/{facility_id}/activate",
        "/api/v1/facilities/{facility_id}/deactivate",
        "/api/v1/facilities/{facility_id}/departments",
        "/api/v1/departments/{department_id}",
        "/api/v1/departments/{department_id}/rooms",
    ):
        assert path in schema["paths"]
