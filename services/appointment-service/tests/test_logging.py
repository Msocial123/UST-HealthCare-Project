import json
import logging

from app.core.logging import JsonFormatter
from tests.conftest import at, bearer, booking_payload, mint_token


def _rendered(caplog) -> str:
    records = [record for record in caplog.records if record.name != "httpx"]
    return "\n".join(JsonFormatter().format(record) for record in records)


def test_requests_never_log_tokens_or_request_values(client, caplog, provider_id) -> None:
    caplog.set_level(logging.DEBUG)
    token = mint_token(["ADMIN"])
    payload = booking_payload(provider_id, reason_code="SYNTHETIC_REASON")
    created = client.post("/api/v1/appointments", json=payload, headers=bearer(token)).json()
    client.post("/api/v1/appointments", json=payload, headers=bearer(token))  # 409 conflict
    client.post(
        "/api/v1/appointments", json={**payload, "reason_code": "Secret free text"}, headers=bearer(token)
    )
    client.post(
        f"/api/v1/appointments/{created['id']}/cancel",
        json={"cancellation_reason": "CANCEL_SECRET"},
        headers=bearer(token),
    )
    client.get("/api/v1/appointments", params={"patient_id": payload["patient_id"]}, headers=bearer(token))
    client.get("/api/v1/appointments", headers=bearer("garbage-token-value"))
    client.post("/api/v1/appointments", json=payload, headers=bearer(mint_token(["DOCTOR"])))

    rendered = _rendered(caplog)
    for sensitive in (
        token,
        "garbage-token-value",
        payload["patient_id"],
        provider_id,
        created["id"],
        "SYNTHETIC_REASON",
        "Secret free text",
        "CANCEL_SECRET",
        at(4, 9)[:16],
    ):
        assert sensitive not in rendered

    events = [getattr(record, "event", None) for record in caplog.records]
    assert "token_rejected" in events
    assert "permission_denied" in events
    assert "http_request" in events


def test_validation_errors_do_not_echo_submitted_values(client, admin, provider_id) -> None:
    payload = booking_payload(provider_id, reason_code="Contains free text")
    response = client.post("/api/v1/appointments", json=payload, headers=admin)
    assert response.status_code == 422
    assert "Contains free text" not in response.text


def test_json_formatter_outputs_structured_fields() -> None:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "hello", None, None)
    record.event = "unit_test"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello" and payload["event"] == "unit_test"
    assert payload["timestamp"].endswith("+00:00")


def test_request_log_uses_endpoint_name_not_raw_path(client, caplog, admin, book, provider_id) -> None:
    created = book(provider_id)
    caplog.set_level(logging.INFO)
    caplog.clear()
    client.get(f"/api/v1/appointments/{created['id']}", headers=admin)
    client.get("/api/v1/unknown/patient-jane-doe-1984-02-03", headers=admin)
    routes = [record.route for record in caplog.records if getattr(record, "event", None) == "http_request"]
    assert routes == ["get_appointment", "<unmatched>"]
    assert not any(hasattr(record, "path") for record in caplog.records)
    rendered = _rendered(caplog)
    assert created["id"] not in rendered and "jane-doe" not in rendered
