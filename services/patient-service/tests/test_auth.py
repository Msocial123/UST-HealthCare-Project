"""Token verification (identity-service contract) and server-side role checks."""

import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from app.domain.roles import Role
from tests.conftest import TEST_SECRET, bearer, make_settings, mint_token, token_claims

PATIENTS_URL = "/api/v1/patients"
OTHER_SECRET = "a-different-unit-test-key-" + "z" * 48


def _valid_payload() -> dict:
    return {"first_name": "Robin", "last_name": "Sample", "date_of_birth": "1985-02-03", "sex": "FEMALE"}


def _endpoints(patient_id: uuid.UUID) -> dict[str, tuple[str, str, dict | None]]:
    return {
        "create": ("post", PATIENTS_URL, _valid_payload()),
        "list": ("get", PATIENTS_URL, None),
        "get": ("get", f"{PATIENTS_URL}/{patient_id}", None),
        "update": ("patch", f"{PATIENTS_URL}/{patient_id}", {"city": "Testville"}),
        "deactivate": ("post", f"{PATIENTS_URL}/{patient_id}/deactivate", None),
    }


ALLOWED = {
    "create": {Role.RECEPTIONIST, Role.ADMIN},
    "list": {Role.RECEPTIONIST, Role.DOCTOR, Role.ADMIN},
    "get": {Role.RECEPTIONIST, Role.DOCTOR, Role.ADMIN},
    "update": {Role.RECEPTIONIST, Role.ADMIN},
    "deactivate": {Role.ADMIN},
}


def _call(client: TestClient, endpoint: tuple[str, str, dict | None], headers: dict | None = None):
    method, url, body = endpoint
    return client.request(method, url, json=body, headers=headers or {})


# --- 401: authentication -----------------------------------------------------------------------


@pytest.mark.parametrize("name", list(ALLOWED))
def test_missing_token_is_401(client: TestClient, name: str) -> None:
    response = _call(client, _endpoints(uuid.uuid4())[name])
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "not_authenticated", "message": "Not authenticated"}}
    assert response.headers["WWW-Authenticate"] == "Bearer"


def _expired() -> str:
    claims = token_claims(["ADMIN"])
    return mint_token(["ADMIN"], iat=claims["iat"] - 3600, nbf=claims["iat"] - 3600, exp=claims["iat"] - 600)


INVALID_TOKENS = {
    "garbage": lambda: "not-a-jwt",
    "expired": _expired,
    "wrong_signature": lambda: mint_token(["ADMIN"], key=OTHER_SECRET),
    "wrong_issuer": lambda: mint_token(["ADMIN"], iss="https://evil.example"),
    "wrong_audience": lambda: mint_token(["ADMIN"], aud="some-other-api"),
    "unknown_kid": lambda: mint_token(["ADMIN"], kid="unknown"),
    "missing_kid": lambda: mint_token(["ADMIN"], kid=None),
    "other_hmac_alg": lambda: mint_token(["ADMIN"], alg="HS512", key=TEST_SECRET + "x" * 16),
    "alg_none": lambda: jwt.encode(
        token_claims(["ADMIN"]), None, algorithm="none", headers={"kid": "test-k1"}
    ),
    "not_yet_valid": lambda: mint_token(["ADMIN"], nbf=token_claims()["iat"] + 3600),
    "not_access_token": lambda: mint_token(["ADMIN"], token_use="refresh"),
    "missing_token_use": lambda: mint_token(["ADMIN"], token_use=None),
    "missing_jti": lambda: mint_token(["ADMIN"], jti=None),
    "missing_exp": lambda: mint_token(["ADMIN"], exp=None),
    "non_uuid_subject": lambda: mint_token(["ADMIN"], sub="user-42"),
    "unknown_role": lambda: mint_token(["SUPERUSER"]),
    "empty_roles": lambda: mint_token([]),
    "roles_not_list": lambda: mint_token("ADMIN"),  # type: ignore[arg-type],
}


@pytest.mark.parametrize("kind", list(INVALID_TOKENS))
def test_invalid_tokens_are_401(client: TestClient, kind: str) -> None:
    response = client.get(PATIENTS_URL, headers=bearer(INVALID_TOKENS[kind]()))
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "not_authenticated", "message": "Invalid or expired token"}}
    assert response.headers["WWW-Authenticate"] == 'Bearer error="invalid_token"'


def test_non_bearer_scheme_is_401(client: TestClient) -> None:
    response = client.get(PATIENTS_URL, headers={"Authorization": f"Basic {mint_token(['ADMIN'])}"})
    assert response.status_code == 401


def test_token_within_leeway_is_accepted(client: TestClient) -> None:
    now = token_claims()["iat"]
    token = mint_token(["DOCTOR"], iat=now - 900, nbf=now - 900, exp=now - 10)
    assert client.get(PATIENTS_URL, headers=bearer(token)).status_code == 200


def test_previous_rotation_key_is_accepted() -> None:
    from fastapi.testclient import TestClient as Client

    from app.db.base import Base
    from app.main import create_app

    app = create_app(
        make_settings(jwt_key_id="k2", jwt_secret_key=OTHER_SECRET, jwt_previous_keys={"k1": TEST_SECRET})
    )
    Base.metadata.create_all(app.state.engine)
    with Client(app) as client:
        assert client.get(PATIENTS_URL, headers=bearer(mint_token(["DOCTOR"], kid="k1"))).status_code == 200
        assert (
            client.get(
                PATIENTS_URL, headers=bearer(mint_token(["DOCTOR"], kid="k2", key=OTHER_SECRET))
            ).status_code
            == 200
        )
        assert client.get(PATIENTS_URL, headers=bearer(mint_token(["DOCTOR"], kid="k2"))).status_code == 401
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()


# --- 403: authorization ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "role"),
    [(name, role) for name, allowed in ALLOWED.items() for role in Role if role not in allowed],
)
def test_roles_without_permission_are_403(
    client: TestClient, auth_headers, make_patient, name: str, role: Role
) -> None:
    patient = make_patient()
    response = _call(client, _endpoints(patient.id)[name], auth_headers(role))
    assert response.status_code == 403
    assert response.json() == {"error": {"code": "forbidden", "message": "Insufficient permissions"}}


@pytest.mark.parametrize(
    ("name", "role"),
    [(name, role) for name, allowed in ALLOWED.items() for role in allowed],
)
def test_roles_with_permission_are_allowed(
    client: TestClient, auth_headers, make_patient, name: str, role: Role
) -> None:
    patient = make_patient()
    response = _call(client, _endpoints(patient.id)[name], auth_headers(role))
    assert response.status_code in {200, 201}


def test_role_in_request_body_is_never_trusted(client: TestClient, auth_headers) -> None:
    response = client.post(
        PATIENTS_URL, json={**_valid_payload(), "role": "ADMIN"}, headers=auth_headers(Role.DOCTOR)
    )
    assert response.status_code == 403


def test_auth_is_checked_before_validation(client: TestClient) -> None:
    assert client.post(PATIENTS_URL, json={"bogus": True}).status_code == 401
