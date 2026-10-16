import json
import logging

from app.core.logging import JsonFormatter
from tests.conftest import bearer, facility_payload, mint_token


def test_requests_never_log_tokens_or_request_values(client, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    token = mint_token(["ADMIN"])
    payload = facility_payload(main_phone="+91 80 5550 0142", address_line1="77 Logcheck Lane")

    client.post("/api/v1/facilities", json=payload, headers=bearer(token))
    client.get("/api/v1/facilities", params={"search": "Searchterm"}, headers=bearer(token))
    client.post("/api/v1/facilities", json={**payload, "timezone": "Mars/Olympus"}, headers=bearer(token))
    client.get("/api/v1/facilities", headers=bearer("garbage-token-value"))
    client.post("/api/v1/facilities", json=payload, headers=bearer(mint_token(["DOCTOR"])))

    records = [record for record in caplog.records if record.name != "httpx"]
    rendered = "\n".join(JsonFormatter().format(record) for record in records)
    for sensitive in (token, "garbage-token-value", "+91 80 5550 0142", "77 Logcheck Lane", "Searchterm"):
        assert sensitive not in rendered

    events = [getattr(record, "event", None) for record in records]
    assert "token_rejected" in events
    assert "permission_denied" in events
    assert "http_request" in events


def test_json_formatter_outputs_structured_fields() -> None:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "hello", None, None)
    record.event = "unit_test"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello" and payload["event"] == "unit_test"
    assert payload["timestamp"].endswith("+00:00")
