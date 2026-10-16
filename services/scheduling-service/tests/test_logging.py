import json
import logging

from app.core.logging import JsonFormatter
from tests.conftest import bearer, mint_token, working_hours_payload


def test_requests_never_log_tokens_or_request_values(client, caplog, facility_id, provider_id) -> None:
    caplog.set_level(logging.DEBUG)
    token = mint_token(["ADMIN"])
    url = f"/api/v1/providers/{provider_id}/working-hours"

    client.post(url, json=working_hours_payload(facility_id, start_local_time="07:17"), headers=bearer(token))
    client.post(
        f"/api/v1/providers/{provider_id}/exceptions",
        json={"starts_at": "x", "ends_at": "y", "type": "LEAVE", "reason_code": "Secret reason text"},
        headers=bearer(token),
    )
    client.get(
        f"/api/v1/providers/{provider_id}/slots",
        params={"facility_id": facility_id, "date_from": "2031-07-17", "date_to": "2031-07-17"},
        headers=bearer(token),
    )
    client.get(url, headers=bearer("garbage-token-value"))
    client.post(url, json=working_hours_payload(facility_id), headers=bearer(mint_token(["DOCTOR"])))

    records = [record for record in caplog.records if record.name != "httpx"]
    rendered = "\n".join(JsonFormatter().format(record) for record in records)
    for sensitive in (token, "garbage-token-value", "07:17", "Secret reason text", "2031-07-17"):
        assert sensitive not in rendered

    events = [getattr(record, "event", None) for record in records]
    assert "token_rejected" in events
    assert "permission_denied" in events
    assert "http_request" in events


def test_validation_errors_do_not_echo_submitted_values(client, facility_id, provider_id) -> None:
    response = client.post(
        f"/api/v1/providers/{provider_id}/exceptions",
        json={
            "starts_at": "2026-04-06T09:00:00Z",
            "ends_at": "2026-04-06T10:00:00Z",
            "type": "LEAVE",
            "reason_code": "Contains free text",
        },
        headers=bearer(mint_token(["ADMIN"])),
    )
    assert response.status_code == 422
    assert "Contains free text" not in response.text


def test_json_formatter_outputs_structured_fields() -> None:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "hello", None, None)
    record.event = "unit_test"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello" and payload["event"] == "unit_test"
    assert payload["timestamp"].endswith("+00:00")
