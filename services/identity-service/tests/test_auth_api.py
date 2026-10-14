from datetime import timedelta

import jwt
from fastapi.testclient import TestClient

from app.core.time import utcnow
from app.domain.roles import Role
from tests.conftest import DEFAULT_PASSWORD, TEST_AUDIENCE, TEST_SECRET

LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"


def _login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD):
    return client.post(LOGIN_URL, json={"email": email, "password": password})


def test_valid_login_issues_token(client: TestClient, make_user) -> None:
    user = make_user(Role.RECEPTIONIST)
    response = _login(client, user.email)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    payload = jwt.decode(body["access_token"], TEST_SECRET, algorithms=["HS256"], audience=TEST_AUDIENCE)
    assert payload["sub"] == str(user.id)
    assert payload["roles"] == ["RECEPTIONIST"]


def test_login_email_is_case_insensitive(client: TestClient, make_user) -> None:
    user = make_user()
    assert _login(client, user.email.upper()).status_code == 200


def test_login_records_last_login(client: TestClient, make_user, db_session) -> None:
    user = make_user()
    assert user.last_login_at is None
    _login(client, user.email)
    db_session.refresh(user)
    assert user.last_login_at is not None
    assert user.last_login_at.tzinfo is not None


def test_bad_password_rejected(client: TestClient, make_user) -> None:
    user = make_user()
    response = _login(client, user.email, "Wrong-Password-000")
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "not_authenticated", "message": "Invalid credentials"}}
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_unknown_user_gets_identical_response(client: TestClient, make_user) -> None:
    user = make_user()
    wrong_password = _login(client, user.email, "Wrong-Password-000")
    unknown = _login(client, "nobody@test.smarthospital.example")
    assert unknown.status_code == 401
    assert unknown.json() == wrong_password.json()


def test_disabled_account_cannot_login(client: TestClient, make_user) -> None:
    user = make_user(is_active=False)
    response = _login(client, user.email)
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid credentials"


def test_login_validation_errors_do_not_echo_password(client: TestClient) -> None:
    secret_password = "Do-Not-Echo-This-Password"
    response = client.post(LOGIN_URL, json={"email": "not-an-email", "password": secret_password})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert secret_password not in response.text


def test_login_missing_fields(client: TestClient) -> None:
    response = client.post(LOGIN_URL, json={})
    assert response.status_code == 422
    locations = {tuple(item["loc"]) for item in response.json()["error"]["details"]}
    assert {("body", "email"), ("body", "password")} <= locations


def test_me_returns_current_user(client: TestClient, make_user) -> None:
    user = make_user(Role.DOCTOR, full_name="Dr. Synthetic Example")
    token = _login(client, user.email).json()["access_token"]
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["role"] == "DOCTOR"
    assert body["full_name"] == "Dr. Synthetic Example"
    assert "password_hash" not in body
    assert "password" not in body


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.get(ME_URL)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "not_authenticated"


def test_non_bearer_scheme_returns_401(client: TestClient) -> None:
    response = client.get(ME_URL, headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert response.status_code == 401


def test_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get(ME_URL, headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == 'Bearer error="invalid_token"'
    assert response.json()["error"]["message"] == "Invalid or expired token"


def test_expired_token_returns_401(client: TestClient, app, make_user) -> None:
    user = make_user()
    expired = app.state.token_service.issue_access_token(
        user.id, Role(user.role), now=utcnow() - timedelta(hours=2)
    ).token
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_token_signed_with_other_key_returns_401(client: TestClient, make_user) -> None:
    user = make_user(Role.ADMIN)
    now = int(utcnow().timestamp())
    forged = jwt.encode(
        {"sub": str(user.id), "roles": ["ADMIN"], "iat": now, "nbf": now, "exp": now + 60},
        "attacker-controlled-key-" + "a" * 40,
        algorithm="HS256",
        headers={"kid": "test-k1"},
    )
    assert client.get(ME_URL, headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_of_user_disabled_after_issue_is_rejected(client, make_user, token_for, db_session) -> None:
    user = make_user()
    token = token_for(user)
    user.is_active = False
    db_session.commit()
    assert client.get(ME_URL, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_of_deleted_user_is_rejected(client, make_user, token_for, db_session) -> None:
    user = make_user()
    token = token_for(user)
    db_session.delete(user)
    db_session.commit()
    assert client.get(ME_URL, headers={"Authorization": f"Bearer {token}"}).status_code == 401
