import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.domain.roles import Role
from app.models.user import User

USERS_URL = "/api/v1/users"
NEW_PASSWORD = "Another-Synthetic-Pass-456"
NON_ADMIN_ROLES = [Role.RECEPTIONIST, Role.DOCTOR, Role.READ_ONLY]


def _new_user_payload(**overrides: object) -> dict:
    payload = {
        "email": "new.receptionist@test.smarthospital.example",
        "full_name": "  Synthetic Receptionist  ",
        "role": "RECEPTIONIST",
        "password": NEW_PASSWORD,
    }
    payload.update(overrides)
    return payload


# --- authorization -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", USERS_URL),
        ("post", USERS_URL),
        ("get", f"{USERS_URL}/{uuid.uuid4()}"),
        ("patch", f"{USERS_URL}/{uuid.uuid4()}"),
        ("post", f"{USERS_URL}/{uuid.uuid4()}/password"),
    ],
)
def test_user_management_requires_authentication(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={})
    assert response.status_code == 401


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_non_admin_roles_are_forbidden(client: TestClient, auth_headers, make_user, role: Role) -> None:
    headers = auth_headers(role)
    target = make_user()
    requests = [
        client.get(USERS_URL, headers=headers),
        client.post(USERS_URL, json=_new_user_payload(), headers=headers),
        client.get(f"{USERS_URL}/{target.id}", headers=headers),
        client.patch(f"{USERS_URL}/{target.id}", json={"role": "ADMIN"}, headers=headers),
        client.post(
            f"{USERS_URL}/{target.id}/password", json={"new_password": NEW_PASSWORD}, headers=headers
        ),
    ]
    for response in requests:
        assert response.status_code == 403
        assert response.json() == {"error": {"code": "forbidden", "message": "Insufficient permissions"}}


def test_role_in_db_wins_over_role_in_token(client: TestClient, app, make_user) -> None:
    user = make_user(Role.READ_ONLY)
    # A validly signed token claiming ADMIN does not elevate a READ_ONLY account in this service.
    token = app.state.token_service.issue_access_token(user.id, Role.ADMIN).token
    assert client.get(USERS_URL, headers={"Authorization": f"Bearer {token}"}).status_code == 403


# --- create ------------------------------------------------------------------------------------


def test_admin_creates_user_and_password_is_hashed(client: TestClient, auth_headers, db_session) -> None:
    response = client.post(USERS_URL, json=_new_user_payload(), headers=auth_headers())

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.receptionist@test.smarthospital.example"
    assert body["full_name"] == "Synthetic Receptionist"
    assert body["role"] == "RECEPTIONIST"
    assert body["is_active"] is True
    assert "password" not in body and "password_hash" not in body

    stored = db_session.scalar(select(User).where(User.id == uuid.UUID(body["id"])))
    assert stored.password_hash != NEW_PASSWORD
    assert NEW_PASSWORD not in stored.password_hash
    assert stored.password_hash.startswith("$argon2id$")

    login = client.post("/api/v1/auth/login", json={"email": body["email"], "password": NEW_PASSWORD})
    assert login.status_code == 200


def test_create_normalizes_email_and_rejects_duplicates(client: TestClient, auth_headers) -> None:
    headers = auth_headers()
    first = client.post(
        USERS_URL, json=_new_user_payload(email="Mixed.Case@Test.SmartHospital.Example"), headers=headers
    )
    assert first.status_code == 201
    assert first.json()["email"] == "mixed.case@test.smarthospital.example"

    duplicate = client.post(
        USERS_URL, json=_new_user_payload(email="MIXED.case@test.smarthospital.example"), headers=headers
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"


@pytest.mark.parametrize(
    "overrides",
    [
        {"password": "short"},
        {"password": " " * 20},
        {"password": "x" * 129},
        {"role": "SUPERUSER"},
        {"email": "not-an-email"},
        {"full_name": "   "},
        {"is_admin": True},
    ],
)
def test_create_validation_errors(client: TestClient, auth_headers, overrides: dict) -> None:
    response = client.post(USERS_URL, json=_new_user_payload(**overrides), headers=auth_headers())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# --- read / list -------------------------------------------------------------------------------


def test_get_user(client: TestClient, auth_headers, make_user) -> None:
    target = make_user(Role.DOCTOR)
    response = client.get(f"{USERS_URL}/{target.id}", headers=auth_headers())
    assert response.status_code == 200
    assert response.json()["id"] == str(target.id)


def test_get_unknown_user_returns_404(client: TestClient, auth_headers) -> None:
    response = client.get(f"{USERS_URL}/{uuid.uuid4()}", headers=auth_headers())
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "User not found"}}


def test_get_user_with_invalid_id_returns_422(client: TestClient, auth_headers) -> None:
    assert client.get(f"{USERS_URL}/not-a-uuid", headers=auth_headers()).status_code == 422


def test_list_users_paginates(client: TestClient, auth_headers, make_user) -> None:
    headers = auth_headers()  # creates 1 admin
    for _ in range(4):
        make_user(Role.DOCTOR)

    first = client.get(USERS_URL, params={"limit": 2, "offset": 0}, headers=headers).json()
    second = client.get(USERS_URL, params={"limit": 2, "offset": 2}, headers=headers).json()
    last = client.get(USERS_URL, params={"limit": 2, "offset": 4}, headers=headers).json()

    assert first["total"] == 5 and first["limit"] == 2 and first["offset"] == 0
    assert len(first["items"]) == 2 and len(second["items"]) == 2 and len(last["items"]) == 1
    ids = [item["id"] for page in (first, second, last) for item in page["items"]]
    assert len(set(ids)) == 5


def test_list_users_filters(client: TestClient, auth_headers, make_user) -> None:
    headers = auth_headers()
    make_user(Role.DOCTOR)
    make_user(Role.DOCTOR, is_active=False)
    make_user(Role.READ_ONLY)

    doctors = client.get(USERS_URL, params={"role": "DOCTOR"}, headers=headers).json()
    assert doctors["total"] == 2
    active_doctors = client.get(
        USERS_URL, params={"role": "DOCTOR", "is_active": "true"}, headers=headers
    ).json()
    assert active_doctors["total"] == 1
    disabled = client.get(USERS_URL, params={"is_active": "false"}, headers=headers).json()
    assert disabled["total"] == 1


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"role": "NOPE"}])
def test_list_users_invalid_query(client: TestClient, auth_headers, params: dict) -> None:
    assert client.get(USERS_URL, params=params, headers=auth_headers()).status_code == 422


# --- update ------------------------------------------------------------------------------------


def test_admin_changes_role_and_disables_user(client: TestClient, auth_headers, make_user) -> None:
    headers = auth_headers()
    target = make_user(Role.READ_ONLY)

    response = client.patch(
        f"{USERS_URL}/{target.id}", json={"role": "DOCTOR", "full_name": "Renamed Synthetic"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["role"] == "DOCTOR"
    assert response.json()["full_name"] == "Renamed Synthetic"

    response = client.patch(f"{USERS_URL}/{target.id}", json={"is_active": False}, headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    from tests.conftest import DEFAULT_PASSWORD

    login = client.post("/api/v1/auth/login", json={"email": target.email, "password": DEFAULT_PASSWORD})
    assert login.status_code == 401


def test_admin_cannot_disable_self(client: TestClient, make_user, auth_headers) -> None:
    admin = make_user(Role.ADMIN)
    response = client.patch(
        f"{USERS_URL}/{admin.id}", json={"is_active": False}, headers=auth_headers(user=admin)
    )
    assert response.status_code == 409


def test_admin_cannot_demote_self(client: TestClient, make_user, auth_headers) -> None:
    admin = make_user(Role.ADMIN)
    response = client.patch(
        f"{USERS_URL}/{admin.id}", json={"role": "READ_ONLY"}, headers=auth_headers(user=admin)
    )
    assert response.status_code == 409


def test_admin_can_rename_self(client: TestClient, make_user, auth_headers) -> None:
    admin = make_user(Role.ADMIN)
    response = client.patch(
        f"{USERS_URL}/{admin.id}",
        json={"full_name": "Synthetic Admin", "role": "ADMIN"},
        headers=auth_headers(user=admin),
    )
    assert response.status_code == 200


@pytest.mark.parametrize("payload", [{}, {"role": None}, {"is_active": None}, {"password": "x" * 20}])
def test_update_validation_errors(client: TestClient, auth_headers, make_user, payload: dict) -> None:
    target = make_user()
    assert client.patch(f"{USERS_URL}/{target.id}", json=payload, headers=auth_headers()).status_code == 422


def test_update_unknown_user_returns_404(client: TestClient, auth_headers) -> None:
    response = client.patch(f"{USERS_URL}/{uuid.uuid4()}", json={"role": "DOCTOR"}, headers=auth_headers())
    assert response.status_code == 404


# --- password reset ----------------------------------------------------------------------------


def test_admin_resets_password(client: TestClient, auth_headers, make_user) -> None:
    target = make_user()
    response = client.post(
        f"{USERS_URL}/{target.id}/password", json={"new_password": NEW_PASSWORD}, headers=auth_headers()
    )
    assert response.status_code == 204

    from tests.conftest import DEFAULT_PASSWORD

    old = client.post("/api/v1/auth/login", json={"email": target.email, "password": DEFAULT_PASSWORD})
    new = client.post("/api/v1/auth/login", json={"email": target.email, "password": NEW_PASSWORD})
    assert old.status_code == 401
    assert new.status_code == 200


def test_reset_password_validation_and_not_found(client: TestClient, auth_headers, make_user) -> None:
    headers = auth_headers()
    target = make_user()
    weak = client.post(f"{USERS_URL}/{target.id}/password", json={"new_password": "short"}, headers=headers)
    assert weak.status_code == 422
    missing = client.post(
        f"{USERS_URL}/{uuid.uuid4()}/password", json={"new_password": NEW_PASSWORD}, headers=headers
    )
    assert missing.status_code == 404
