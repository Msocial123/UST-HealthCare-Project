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
        "/api/v1/appointments",
        "/api/v1/appointments/{appointment_id}",
        "/api/v1/appointments/{appointment_id}/reschedule",
        "/api/v1/appointments/{appointment_id}/cancel",
        "/api/v1/appointments/{appointment_id}/check-in",
        "/api/v1/appointments/{appointment_id}/complete",
        "/api/v1/appointments/{appointment_id}/no-show",
    ):
        assert path in schema["paths"]
    assert "HTTPBearer" in schema["components"]["securitySchemes"]
    assert "503" in schema["paths"]["/api/v1/appointments"]["post"]["responses"]
