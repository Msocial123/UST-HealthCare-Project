import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from tests.conftest import ALL_ROLES, TEST_SECRET, FakeFacilityClient, bearer, make_settings, mint_token

_ID = uuid.uuid4()
_FACILITY = uuid.uuid4()
_SLOTS = f"/api/v1/providers/{_ID}/slots?facility_id={_FACILITY}&date_from=2026-04-06&date_to=2026-04-07"
_EXCEPTIONS_RANGE = "from=2026-04-01T00:00:00Z&to=2026-04-30T00:00:00Z"

# (method, path, roles allowed by the KAN-9 permission table)
ENDPOINTS = [
    ("post", f"/api/v1/providers/{_ID}/working-hours", {"ADMIN"}),
    ("get", f"/api/v1/providers/{_ID}/working-hours", set(ALL_ROLES)),
    ("patch", f"/api/v1/working-hours/{_ID}", {"ADMIN"}),
    ("delete", f"/api/v1/working-hours/{_ID}", {"ADMIN"}),
    ("post", f"/api/v1/providers/{_ID}/exceptions", {"ADMIN", "RECEPTIONIST"}),
    ("get", f"/api/v1/providers/{_ID}/exceptions?{_EXCEPTIONS_RANGE}", set(ALL_ROLES)),
    ("patch", f"/api/v1/exceptions/{_ID}", {"ADMIN", "RECEPTIONIST"}),
    ("delete", f"/api/v1/exceptions/{_ID}", {"ADMIN", "RECEPTIONIST"}),
    ("get", _SLOTS, {"ADMIN", "RECEPTIONIST", "DOCTOR"}),
]
FORBIDDEN = [
    (method, path, role) for method, path, allowed in ENDPOINTS for role in ALL_ROLES if role not in allowed
]
ALLOWED = [(method, path, role) for method, path, allowed in ENDPOINTS for role in sorted(allowed)]


def _assert_401(response) -> None:
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert response.headers["WWW-Authenticate"].startswith("Bearer")


def _request(client, method, path, headers=None):
    body = None if method in {"get", "delete"} else {}
    return client.request(method, path, json=body, headers=headers)


@pytest.mark.parametrize(("method", "path"), [(method, path) for method, path, _ in ENDPOINTS])
def test_missing_token_is_401(client, method, path) -> None:
    _assert_401(_request(client, method, path))


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        mint_token(secret="another-secret-that-is-long-enough-" + "z" * 32),
        mint_token(lifetime=timedelta(minutes=-10)),
        mint_token(now=datetime.now(UTC) + timedelta(hours=1)),
        mint_token(iss="https://evil.example"),
        mint_token(aud="another-audience"),
        mint_token(kid="unknown-kid"),
        mint_token(kid=None),
        mint_token(algorithm="HS512", secret=TEST_SECRET + "x" * 64),
        mint_token(token_use="refresh"),
        mint_token(drop=("jti",)),
        mint_token(drop=("exp",)),
        mint_token(sub="not-a-uuid"),
        mint_token(roles=[]),
        mint_token(roles=["SUPERUSER"]),
        mint_token(roles="ADMIN"),
    ],
    ids=[
        "malformed",
        "bad-signature",
        "expired",
        "not-yet-valid",
        "wrong-issuer",
        "wrong-audience",
        "unknown-kid",
        "missing-kid",
        "unexpected-algorithm",
        "not-access-token",
        "missing-jti",
        "missing-exp",
        "sub-not-uuid",
        "empty-roles",
        "unknown-role",
        "roles-not-list",
    ],
)
@pytest.mark.parametrize(("method", "path"), [(method, path) for method, path, _ in ENDPOINTS[:2]])
def test_invalid_tokens_are_401(client, token, method, path) -> None:
    response = _request(client, method, path, bearer(token))
    _assert_401(response)
    assert response.json()["error"]["message"] == "Invalid or expired token"


@pytest.mark.parametrize(("method", "path"), [(method, path) for method, path, _ in ENDPOINTS])
def test_expired_token_is_401_on_every_endpoint(client, method, path) -> None:
    _assert_401(_request(client, method, path, bearer(mint_token(lifetime=timedelta(minutes=-5)))))


def test_alg_none_token_is_rejected(client) -> None:
    now = int(datetime.now(UTC).timestamp())
    claims = {"iss": "x", "aud": "y", "sub": str(uuid.uuid4()), "iat": now, "nbf": now, "exp": now + 60}
    token = jwt.encode(
        {**claims, "jti": "j", "token_use": "access", "roles": ["ADMIN"]}, None, algorithm="none"
    )
    _assert_401(client.get(f"/api/v1/providers/{_ID}/working-hours", headers=bearer(token)))


def test_non_bearer_scheme_is_401(client) -> None:
    headers = {"Authorization": "Basic dXNlcjpwYXNz"}
    _assert_401(client.get(f"/api/v1/providers/{_ID}/working-hours", headers=headers))


@pytest.mark.parametrize(("method", "path", "role"), FORBIDDEN)
def test_wrong_role_is_403(client, auth, facilities, method, path, role) -> None:
    response = _request(client, method, path, auth(role))
    assert response.status_code == 403
    assert response.json()["error"] == {"code": "forbidden", "message": "Insufficient permissions"}
    assert facilities.calls == []


@pytest.mark.parametrize(("method", "path", "role"), ALLOWED)
def test_allowed_roles_pass_authorization(client, auth, method, path, role) -> None:
    response = _request(client, method, path, auth(role))
    assert response.status_code not in {401, 403}, response.text


def test_caller_supplied_role_headers_are_ignored(client, facility_id, provider_id) -> None:
    from tests.conftest import working_hours_payload

    headers = {**bearer(mint_token(["READ_ONLY"])), "X-Roles": "ADMIN", "X-User-Role": "ADMIN"}
    response = client.post(
        f"/api/v1/providers/{provider_id}/working-hours?role=ADMIN",
        json={**working_hours_payload(facility_id), "roles": ["ADMIN"]},
        headers=headers,
    )
    assert response.status_code == 403


def test_previous_rotation_key_is_accepted() -> None:
    from fastapi.testclient import TestClient

    from app.db.base import Base
    from app.main import create_app

    old_secret = "previous-unit-test-key-" + "p" * 40
    app = create_app(
        make_settings(jwt_previous_keys={"test-k0": old_secret}), facility_client=FakeFacilityClient()
    )
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        token = mint_token(["READ_ONLY"], secret=old_secret, kid="test-k0")
        response = client.get(f"/api/v1/providers/{_ID}/working-hours", headers=bearer(token))
        assert response.status_code == 200
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()
