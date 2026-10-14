import json
import logging

from app.core.logging import JsonFormatter
from app.domain.roles import Role
from tests.conftest import DEFAULT_PASSWORD


def test_auth_flow_never_logs_passwords_or_tokens(client, make_user, caplog) -> None:
    user = make_user(Role.ADMIN)
    caplog.set_level(logging.DEBUG)

    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD})
    token = login.json()["access_token"]
    client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    client.post("/api/v1/auth/login", json={"email": user.email, "password": "Wrong-But-Secret-999"})
    client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage-token-value"})

    formatter = JsonFormatter()
    rendered = "\n".join(formatter.format(record) for record in caplog.records)
    for sensitive in (DEFAULT_PASSWORD, "Wrong-But-Secret-999", token, "garbage-token-value", user.email):
        assert sensitive not in rendered

    events = [getattr(record, "event", None) for record in caplog.records]
    assert "login_succeeded" in events
    assert "login_failed" in events
    assert "token_rejected" in events
    assert "http_request" in events


def test_json_formatter_outputs_structured_fields() -> None:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "hello", None, None)
    record.event = "unit_test"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello"
    assert payload["event"] == "unit_test"
    assert payload["level"] == "INFO"
    assert payload["timestamp"].endswith("+00:00")
