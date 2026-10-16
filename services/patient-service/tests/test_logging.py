import json
import logging

from app.core.logging import JsonFormatter
from app.domain.roles import Role
from tests.conftest import bearer

PATIENTS_URL = "/api/v1/patients"


def test_patient_flows_never_log_tokens_or_patient_data(client, auth_headers, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    headers = auth_headers(Role.ADMIN)
    payload = {
        "first_name": "Quincy",
        "last_name": "Logcheck",
        "date_of_birth": "1966-07-08",
        "sex": "OTHER",
        "phone": "+1 555 0199",
        "email": "quincy.logcheck@example.com",
        "address_line1": "99 Hidden Lane",
    }
    created = client.post(PATIENTS_URL, json=payload, headers=headers).json()
    client.get(PATIENTS_URL, params={"search": "Logcheck 1966-07-08"}, headers=headers)
    client.patch(f"{PATIENTS_URL}/{created['id']}", json={"city": "Secretcity"}, headers=headers)
    client.post(f"{PATIENTS_URL}/{created['id']}/deactivate", headers=headers)
    client.get(PATIENTS_URL, headers=bearer("garbage-token-value"))

    # Records from the test's own HTTP client ("httpx") are not emitted by the service.
    records = [record for record in caplog.records if record.name != "httpx"]
    rendered = "\n".join(JsonFormatter().format(record) for record in records)
    token = headers["Authorization"].removeprefix("Bearer ")
    sensitive = [
        token,
        "garbage-token-value",
        created["medical_record_number"],
        "Secretcity",
        *payload.values(),
    ]
    for value in sensitive:
        assert value not in rendered, value

    events = [getattr(record, "event", None) for record in records]
    for event in (
        "patient_registered",
        "patient_updated",
        "patient_deactivated",
        "token_rejected",
        "http_request",
    ):
        assert event in events


def test_json_formatter_outputs_structured_fields() -> None:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "hello", None, None)
    record.event = "unit_test"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello"
    assert payload["event"] == "unit_test"
    assert payload["timestamp"].endswith("+00:00")
