import json
import logging

from app.core.logging import JsonFormatter
from tests.conftest import bearer, mint_token, provider_payload


def test_requests_never_log_tokens_or_contact_details(client, create_specialty, caplog) -> None:
    specialty = create_specialty("CARDIOLOGY")
    caplog.set_level(logging.DEBUG)
    token = mint_token(["ADMIN"])
    payload = provider_payload(
        [specialty["id"]], work_email="log.check@provider.example", work_phone="+1 555 0142"
    )

    client.post("/api/v1/providers", json=payload, headers=bearer(token))
    client.get("/api/v1/providers", params={"search": "Testwell"}, headers=bearer(token))
    client.get("/api/v1/specialties", headers=bearer("garbage-token-value"))
    client.post(
        "/api/v1/specialties", json={"code": "X1", "name": "X1"}, headers=bearer(mint_token(["DOCTOR"]))
    )

    # httpx records come from the test client itself (it logs full URLs), not from the service.
    records = [record for record in caplog.records if record.name != "httpx"]
    rendered = "\n".join(JsonFormatter().format(record) for record in records)
    for sensitive in (token, "garbage-token-value", "log.check@provider.example", "+1 555 0142", "Testwell"):
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
