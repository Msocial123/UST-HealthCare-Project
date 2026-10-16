import json
import logging
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.clients.facility_client import FACILITY_UNAVAILABLE_MESSAGE, HttpFacilityClient
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.core.logging import JsonFormatter
from app.db.base import Base
from app.main import create_app
from tests.conftest import bearer, make_settings, mint_token

FACILITY_ID = uuid.uuid4()
TOKEN = "synthetic-access-token-value"


def _client(handler) -> HttpFacilityClient:
    return HttpFacilityClient("http://facility.unit-test.local/", 2.0, transport=httpx.MockTransport(handler))


def _facility_body(**overrides) -> dict:
    body = {"id": str(FACILITY_ID), "code": "NHG", "timezone": "Europe/London", "is_active": True}
    body.update(overrides)
    return body


def test_get_facility_success_forwards_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_facility_body())

    info = _client(handler).get_facility(FACILITY_ID, TOKEN)
    assert info.id == FACILITY_ID and info.timezone == "Europe/London" and info.is_active is True
    assert str(seen[0].url) == f"http://facility.unit-test.local/api/v1/facilities/{FACILITY_ID}"
    assert seen[0].method == "GET"
    assert seen[0].headers["Authorization"] == f"Bearer {TOKEN}"


def test_facility_404_is_not_found() -> None:
    client = _client(lambda request: httpx.Response(404, json={"error": {"code": "not_found"}}))
    with pytest.raises(NotFoundError) as excinfo:
        client.get_facility(FACILITY_ID, TOKEN)
    assert excinfo.value.message == "Facility not found"


def _raise(exc: Exception):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


@pytest.mark.parametrize(
    "handler",
    [
        _raise(httpx.ConnectError("connection refused")),
        _raise(httpx.ReadTimeout("timed out")),
        lambda request: httpx.Response(500, json={}),
        lambda request: httpx.Response(502, text="bad gateway"),
        lambda request: httpx.Response(401, json={}),
        lambda request: httpx.Response(302, headers={"Location": "http://elsewhere.example"}),
        lambda request: httpx.Response(200, text="not json"),
        lambda request: httpx.Response(200, json={"id": str(FACILITY_ID)}),
        lambda request: httpx.Response(200, json=_facility_body(timezone="Mars/Olympus")),
        lambda request: httpx.Response(200, json=_facility_body(id=str(uuid.uuid4()))),
    ],
    ids=[
        "connect-error",
        "timeout",
        "500",
        "502",
        "401",
        "redirect",
        "not-json",
        "missing-fields",
        "invalid-timezone",
        "id-mismatch",
    ],
)
def test_facility_failures_are_service_unavailable(handler, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ServiceUnavailableError) as excinfo:
        _client(handler).get_facility(FACILITY_ID, TOKEN)
    assert excinfo.value.status_code == 503
    assert excinfo.value.message == FACILITY_UNAVAILABLE_MESSAGE
    rendered = "\n".join(JsonFormatter().format(record) for record in caplog.records)
    assert TOKEN not in rendered
    assert "facility_unavailable" in rendered


def test_http_client_wired_into_app_returns_503() -> None:
    facility_client = _client(_raise(httpx.ConnectError("connection refused")))
    app = create_app(make_settings(), facility_client=facility_client)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/providers/{uuid.uuid4()}/slots",
            params={"facility_id": str(FACILITY_ID), "date_from": "2026-04-06", "date_to": "2026-04-06"},
            headers=bearer(mint_token(["DOCTOR"])),
        )
    assert response.status_code == 503
    assert json.loads(response.text)["error"]["message"] == FACILITY_UNAVAILABLE_MESSAGE
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()
