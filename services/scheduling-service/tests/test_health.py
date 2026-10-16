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
        "/api/v1/providers/{provider_id}/working-hours",
        "/api/v1/working-hours/{working_hours_id}",
        "/api/v1/providers/{provider_id}/exceptions",
        "/api/v1/exceptions/{exception_id}",
        "/api/v1/providers/{provider_id}/slots",
    ):
        assert path in schema["paths"]
    assert "HTTPBearer" in schema["components"]["securitySchemes"]
