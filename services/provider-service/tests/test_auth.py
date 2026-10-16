import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from tests.conftest import TEST_SECRET, bearer, make_settings, mint_token

PROTECTED = [
    ("get", "/api/v1/specialties"),
    ("post", "/api/v1/specialties"),
    ("patch", f"/api/v1/specialties/{uuid.uuid4()}"),
    ("post", "/api/v1/providers"),
    ("get", "/api/v1/providers"),
    ("get", f"/api/v1/providers/{uuid.uuid4()}"),
    ("patch", f"/api/v1/providers/{uuid.uuid4()}"),
    ("post", f"/api/v1/providers/{uuid.uuid4()}/deactivate"),
    ("post", f"/api/v1/providers/{uuid.uuid4()}/activate"),
]
ADMIN_ONLY = [entry for entry in PROTECTED if entry[0] != "get"]
PROVIDER_READ = [entry for entry in PROTECTED if entry[0] == "get" and "providers" in entry[1]]


def _assert_401(response) -> None:
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert response.headers["WWW-Authenticate"].startswith("Bearer")


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_missing_token_is_401(client, method, path) -> None:
    _assert_401(client.request(method, path, json={}))


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
def test_invalid_tokens_are_401(client, token) -> None:
    response = client.get("/api/v1/specialties", headers=bearer(token))
    _assert_401(response)
    assert response.json()["error"]["message"] == "Invalid or expired token"


def test_alg_none_token_is_rejected(client) -> None:
    now = int(datetime.now(UTC).timestamp())
    claims = {"iss": "x", "aud": "y", "sub": str(uuid.uuid4()), "iat": now, "nbf": now, "exp": now + 60}
    token = jwt.encode(
        {**claims, "jti": "j", "token_use": "access", "roles": ["ADMIN"]}, None, algorithm="none"
    )
    _assert_401(client.get("/api/v1/specialties", headers=bearer(token)))


def test_non_bearer_scheme_is_401(client) -> None:
    _assert_401(client.get("/api/v1/specialties", headers={"Authorization": "Basic dXNlcjpwYXNz"}))


def test_previous_rotation_key_is_accepted() -> None:
    from fastapi.testclient import TestClient

    from app.db.base import Base
    from app.main import create_app

    old_secret = "previous-unit-test-key-" + "p" * 40
    app = create_app(make_settings(jwt_previous_keys={"test-k0": old_secret}))
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        token = mint_token(["READ_ONLY"], secret=old_secret, kid="test-k0")
        assert client.get("/api/v1/specialties", headers=bearer(token)).status_code == 200
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()


def test_caller_supplied_role_headers_are_ignored(client) -> None:
    headers = {**bearer(mint_token(["READ_ONLY"])), "X-Roles": "ADMIN", "X-User-Role": "ADMIN"}
    response = client.post(
        "/api/v1/specialties", json={"code": "NEURO", "name": "Neurology"}, headers=headers
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["RECEPTIONIST", "DOCTOR", "READ_ONLY"])
@pytest.mark.parametrize(("method", "path"), ADMIN_ONLY)
def test_non_admin_cannot_manage(client, auth, role, method, path) -> None:
    response = client.request(method, path, json={}, headers=auth(role))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize(("method", "path"), PROVIDER_READ)
def test_read_only_cannot_read_providers(client, auth, method, path) -> None:
    response = client.request(method, path, headers=auth("READ_ONLY"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize("role", ["ADMIN", "RECEPTIONIST", "DOCTOR", "READ_ONLY"])
def test_any_role_can_list_specialties(client, auth, role) -> None:
    assert client.get("/api/v1/specialties", headers=auth(role)).status_code == 200


@pytest.mark.parametrize("role", ["ADMIN", "RECEPTIONIST", "DOCTOR"])
def test_provider_readers_can_search(client, auth, role) -> None:
    assert client.get("/api/v1/providers", headers=auth(role)).status_code == 200


def test_multi_role_token_uses_union_of_permissions(client) -> None:
    headers = bearer(mint_token(["READ_ONLY", "DOCTOR"]))
    assert client.get("/api/v1/providers", headers=headers).status_code == 200
