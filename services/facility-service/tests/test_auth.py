import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from tests.conftest import TEST_SECRET, bearer, make_settings, mint_token

_ID = uuid.uuid4()
PROTECTED = [
    ("post", "/api/v1/facilities"),
    ("get", "/api/v1/facilities"),
    ("get", f"/api/v1/facilities/{_ID}"),
    ("patch", f"/api/v1/facilities/{_ID}"),
    ("post", f"/api/v1/facilities/{_ID}/deactivate"),
    ("post", f"/api/v1/facilities/{_ID}/activate"),
    ("post", f"/api/v1/facilities/{_ID}/departments"),
    ("get", f"/api/v1/facilities/{_ID}/departments"),
    ("get", f"/api/v1/departments/{_ID}"),
    ("patch", f"/api/v1/departments/{_ID}"),
    ("post", f"/api/v1/departments/{_ID}/rooms"),
    ("get", f"/api/v1/departments/{_ID}/rooms"),
]
ADMIN_ONLY = [entry for entry in PROTECTED if entry[0] != "get"]
ALL_ROLES = ["ADMIN", "RECEPTIONIST", "DOCTOR", "READ_ONLY"]


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
    response = client.get("/api/v1/facilities", headers=bearer(token))
    _assert_401(response)
    assert response.json()["error"]["message"] == "Invalid or expired token"


def test_alg_none_token_is_rejected(client) -> None:
    now = int(datetime.now(UTC).timestamp())
    claims = {"iss": "x", "aud": "y", "sub": str(uuid.uuid4()), "iat": now, "nbf": now, "exp": now + 60}
    token = jwt.encode(
        {**claims, "jti": "j", "token_use": "access", "roles": ["ADMIN"]}, None, algorithm="none"
    )
    _assert_401(client.get("/api/v1/facilities", headers=bearer(token)))


def test_non_bearer_scheme_is_401(client) -> None:
    _assert_401(client.get("/api/v1/facilities", headers={"Authorization": "Basic dXNlcjpwYXNz"}))


def test_previous_rotation_key_is_accepted() -> None:
    from fastapi.testclient import TestClient

    from app.db.base import Base
    from app.main import create_app

    old_secret = "previous-unit-test-key-" + "p" * 40
    app = create_app(make_settings(jwt_previous_keys={"test-k0": old_secret}))
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        token = mint_token(["READ_ONLY"], secret=old_secret, kid="test-k0")
        assert client.get("/api/v1/facilities", headers=bearer(token)).status_code == 200
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()


def test_caller_supplied_role_headers_are_ignored(client) -> None:
    from tests.conftest import facility_payload

    headers = {**bearer(mint_token(["READ_ONLY"])), "X-Roles": "ADMIN", "X-User-Role": "ADMIN"}
    response = client.post("/api/v1/facilities", json=facility_payload(), headers=headers)
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["RECEPTIONIST", "DOCTOR", "READ_ONLY"])
@pytest.mark.parametrize(("method", "path"), ADMIN_ONLY)
def test_non_admin_cannot_manage(client, auth, role, method, path) -> None:
    response = client.request(method, path, json={}, headers=auth(role))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_non_admin_write_on_existing_resources_is_403_and_changes_nothing(
    client, auth, admin, department, create_room
) -> None:
    facility_id = department["facility_id"]
    doctor = auth("DOCTOR")
    attempts = [
        ("patch", f"/api/v1/facilities/{facility_id}", {"name": "Hijacked Name"}),
        ("post", f"/api/v1/facilities/{facility_id}/deactivate", None),
        ("post", f"/api/v1/facilities/{facility_id}/departments", {"code": "ER", "name": "Emergency"}),
        ("patch", f"/api/v1/departments/{department['id']}", {"is_active": False}),
        ("post", f"/api/v1/departments/{department['id']}/rooms", {"room_number": "1", "room_type": "WARD"}),
    ]
    for method, path, body in attempts:
        response = client.request(method, path, json=body, headers=doctor)
        assert response.status_code == 403, path
    facility = client.get(f"/api/v1/facilities/{facility_id}", headers=admin).json()
    assert facility["name"] == "Northwind General Hospital" and facility["is_active"] is True
    assert client.get(f"/api/v1/facilities/{facility_id}/departments", headers=admin).json()["total"] == 1
    assert client.get(f"/api/v1/departments/{department['id']}", headers=admin).json()["is_active"] is True
    assert client.get(f"/api/v1/departments/{department['id']}/rooms", headers=admin).json()["total"] == 0


@pytest.mark.parametrize("role", ALL_ROLES)
def test_any_authenticated_role_can_read(client, auth, department, create_room, role) -> None:
    create_room(department["id"])
    headers = auth(role)
    facility_id = department["facility_id"]
    for path in (
        "/api/v1/facilities",
        f"/api/v1/facilities/{facility_id}",
        f"/api/v1/facilities/{facility_id}/departments",
        f"/api/v1/departments/{department['id']}",
        f"/api/v1/departments/{department['id']}/rooms",
    ):
        assert client.get(path, headers=headers).status_code == 200, path
