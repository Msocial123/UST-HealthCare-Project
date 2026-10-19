import json
import logging
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.clients.scheduling_client import SCHEDULING_UNAVAILABLE_MESSAGE, HttpSchedulingClient
from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError
from app.core.logging import JsonFormatter
from tests.conftest import FakeSchedulingClient, booking_payload, build_app, make_settings, teardown_app

PROVIDER = uuid.uuid4()
FACILITY = uuid.uuid4()
TOKEN = "synthetic-access-token-value"
START = datetime(2030, 3, 4, 9, 0, tzinfo=UTC)
END = datetime(2030, 3, 4, 9, 30, tzinfo=UTC)


def _client(handler) -> HttpSchedulingClient:
    return HttpSchedulingClient(
        "http://scheduling.unit-test.local/", 2.0, transport=httpx.MockTransport(handler)
    )


def _slots(*windows: tuple[str, str]) -> dict:
    return {"slots": [{"start_utc": start, "end_utc": end, "extra": "ignored"} for start, end in windows]}


def test_slots_covering_the_interval_are_available() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json=_slots(
                ("2030-03-04T09:00:00Z", "2030-03-04T09:15:00Z"),
                ("2030-03-04T09:15:00Z", "2030-03-04T09:30:00Z"),
            ),
        )

    assert _client(handler).is_available(PROVIDER, FACILITY, START, END, TOKEN) is True
    request = seen[0]
    assert request.url.path == f"/api/v1/providers/{PROVIDER}/slots"
    assert request.url.params["facility_id"] == str(FACILITY)
    assert request.url.params["date_from"] == "2030-03-03" and request.url.params["date_to"] == "2030-03-05"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize(
    "windows",
    [
        (),
        (("2030-03-04T09:00:00Z", "2030-03-04T09:15:00Z"),),
        (("2030-03-04T09:00:00Z", "2030-03-04T09:10:00Z"), ("2030-03-04T09:15:00Z", "2030-03-04T09:30:00Z")),
    ],
    ids=["no-slots", "partial", "gap"],
)
def test_uncovered_interval_is_not_available(windows) -> None:
    client = _client(lambda request: httpx.Response(200, json=_slots(*windows)))
    assert client.is_available(PROVIDER, FACILITY, START, END, TOKEN) is False


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(404, json={}), NotFoundError),
        (httpx.Response(409, json={}), ConflictError),
        (httpx.Response(500, json={}), ServiceUnavailableError),
        (httpx.Response(200, text="not-json"), ServiceUnavailableError),
        (httpx.Response(200, json={"slots": [{"start_utc": "bad"}]}), ServiceUnavailableError),
    ],
)
def test_upstream_errors_are_mapped(response, error) -> None:
    with pytest.raises(error):
        _client(lambda request: response).is_available(PROVIDER, FACILITY, START, END, TOKEN)


def test_transport_failure_is_503_and_never_logs_the_token(caplog) -> None:
    caplog.set_level(logging.DEBUG)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(ServiceUnavailableError) as excinfo:
        _client(handler).is_available(PROVIDER, FACILITY, START, END, TOKEN)
    assert excinfo.value.message == SCHEDULING_UNAVAILABLE_MESSAGE
    rendered = "\n".join(JsonFormatter().format(record) for record in caplog.records)
    assert TOKEN not in rendered
    assert any(
        json.loads(JsonFormatter().format(r)).get("event") == "scheduling_unavailable" for r in caplog.records
    )


@pytest.fixture
def advised():
    fake = FakeSchedulingClient()
    settings = make_settings(
        scheduling_advice_enabled=True, scheduling_service_url="http://scheduling.unit-test.local"
    )
    app = build_app(settings, scheduling_client=fake)
    with TestClient(app) as client:
        yield client, fake
        teardown_app(app)


def test_booking_consults_scheduling_when_enabled(advised, admin) -> None:
    client, fake = advised
    response = client.post("/api/v1/appointments", json=booking_payload(str(PROVIDER)), headers=admin)
    assert response.status_code == 201
    assert len(fake.calls) == 1 and fake.calls[0][0] == PROVIDER
    assert fake.calls[0][2] == admin["Authorization"].removeprefix("Bearer ")


def test_scheduling_unavailable_time_is_409_and_not_stored(advised, admin) -> None:
    client, fake = advised
    fake.available = False
    response = client.post("/api/v1/appointments", json=booking_payload(str(PROVIDER)), headers=admin)
    assert response.status_code == 409
    assert client.get("/api/v1/appointments", headers=admin).json()["total"] == 0


def test_database_stays_final_authority_when_scheduling_says_available(advised, admin) -> None:
    client, _ = advised
    assert (
        client.post("/api/v1/appointments", json=booking_payload(str(PROVIDER)), headers=admin).status_code
        == 201
    )
    assert (
        client.post("/api/v1/appointments", json=booking_payload(str(PROVIDER)), headers=admin).status_code
        == 409
    )


def test_scheduling_is_not_called_when_advice_disabled(client, admin, provider_id) -> None:
    assert client.app.state.scheduling_client is None
    assert (
        client.post("/api/v1/appointments", json=booking_payload(provider_id), headers=admin).status_code
        == 201
    )
