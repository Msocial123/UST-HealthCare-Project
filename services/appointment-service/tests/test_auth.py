import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from tests.conftest import (
    ALL_ROLES,
    TEST_SECRET,
    bearer,
    booking_payload,
    build_app,
    make_settings,
    mint_token,
)
from tests.conftest import teardown_app as _teardown

_ID = uuid.uuid4()
_BOOKERS = {"ADMIN", "RECEPTIONIST"}
_ALL_STAFF = {"ADMIN", "RECEPTIONIST", "DOCTOR"}

# (method, path, roles allowed by the KAN-10 permission table)
ENDPOINTS = [
    ("post", "/api/v1/appointments", _BOOKERS),
    ("get", "/api/v1/appointments", _ALL_STAFF),
    ("get", f"/api/v1/appointments/{_ID}", _ALL_STAFF),
    ("post", f"/api/v1/appointments/{_ID}/reschedule", _BOOKERS),
    ("post", f"/api/v1/appointments/{_ID}/cancel", _BOOKERS),
    ("post", f"/api/v1/appointments/{_ID}/check-in", _ALL_STAFF),
    ("post", f"/api/v1/appointments/{_ID}/complete", _ALL_STAFF),
    ("post", f"/api/v1/appointments/{_ID}/no-show", _ALL_STAFF),
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
    body = None if method == "get" else {}
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
    _assert_401(client.get("/api/v1/appointments", headers=bearer(token)))


def test_non_bearer_scheme_is_401(client) -> None:
    _assert_401(client.get("/api/v1/appointments", headers={"Authorization": "Basic dXNlcjpwYXNz"}))


@pytest.mark.parametrize(("method", "path", "role"), FORBIDDEN)
def test_wrong_role_is_403(client, auth, method, path, role) -> None:
    response = _request(client, method, path, auth(role))
    assert response.status_code == 403
    assert response.json()["error"] == {"code": "forbidden", "message": "Insufficient permissions"}


@pytest.mark.parametrize(("method", "path", "role"), ALLOWED)
def test_allowed_roles_pass_authorization(client, auth, method, path, role) -> None:
    response = _request(client, method, path, auth(role))
    assert response.status_code not in {401, 403}, response.text


def test_caller_supplied_roles_are_ignored(client, provider_id) -> None:
    headers = {**bearer(mint_token(["DOCTOR"])), "X-Roles": "ADMIN", "X-User-Role": "ADMIN"}
    response = client.post(
        "/api/v1/appointments?role=ADMIN",
        json={**booking_payload(provider_id), "roles": ["ADMIN"]},
        headers=headers,
    )
    assert response.status_code == 403


def test_created_by_comes_from_the_token_subject(client, provider_id) -> None:
    subject = str(uuid.uuid4())
    token = mint_token(["RECEPTIONIST"], sub=subject)
    response = client.post(
        "/api/v1/appointments",
        json={**booking_payload(provider_id), "created_by": str(uuid.uuid4())},
        headers=bearer(token),
    )
    assert response.status_code == 422  # unknown fields are rejected, never trusted
    response = client.post("/api/v1/appointments", json=booking_payload(provider_id), headers=bearer(token))
    assert response.status_code == 201 and response.json()["created_by"] == subject


def test_previous_rotation_key_is_accepted() -> None:
    from fastapi.testclient import TestClient

    old_secret = "previous-unit-test-key-" + "p" * 40
    app = build_app(make_settings(jwt_previous_keys={"test-k0": old_secret}))
    with TestClient(app) as client:
        token = mint_token(["DOCTOR"], secret=old_secret, kid="test-k0")
        assert client.get("/api/v1/appointments", headers=bearer(token)).status_code == 200
        _teardown(app)
