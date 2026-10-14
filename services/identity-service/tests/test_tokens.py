import uuid
from datetime import timedelta

import jwt
import pytest

from app.core.time import utcnow
from app.core.tokens import TokenError, TokenService
from app.domain.roles import Role
from tests.conftest import TEST_AUDIENCE, TEST_ISSUER, TEST_SECRET, make_settings

USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


@pytest.fixture
def service() -> TokenService:
    return TokenService(make_settings())


def _claims(**overrides: object) -> dict:
    now = int(utcnow().timestamp())
    claims = {
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
        "sub": str(USER_ID),
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "jti": str(uuid.uuid4()),
        "token_use": "access",
        "roles": ["DOCTOR"],
    }
    claims.update(overrides)
    return {key: value for key, value in claims.items() if value is not None}


def _encode(claims: dict, *, key: str = TEST_SECRET, kid: str | None = "test-k1", alg: str = "HS256") -> str:
    headers = {"kid": kid} if kid is not None else {}
    return jwt.encode(claims, key, algorithm=alg, headers=headers)


def test_issued_token_contains_contract_claims(service: TokenService) -> None:
    issued = service.issue_access_token(USER_ID, Role.DOCTOR)
    assert issued.expires_in == 15 * 60

    header = jwt.get_unverified_header(issued.token)
    assert header == {"alg": "HS256", "kid": "test-k1", "typ": "JWT"}
    payload = jwt.decode(issued.token, TEST_SECRET, algorithms=["HS256"], audience=TEST_AUDIENCE)
    assert set(payload) == {"iss", "aud", "sub", "iat", "nbf", "exp", "jti", "token_use", "roles"}
    assert payload["iss"] == TEST_ISSUER
    assert payload["sub"] == str(USER_ID)
    assert payload["roles"] == ["DOCTOR"]
    assert payload["token_use"] == "access"
    assert payload["exp"] - payload["iat"] == 15 * 60


def test_round_trip(service: TokenService) -> None:
    claims = service.decode_access_token(service.issue_access_token(USER_ID, Role.ADMIN).token)
    assert claims.subject == USER_ID
    assert claims.roles == (Role.ADMIN,)
    assert claims.expires_at > claims.issued_at


def test_expired_token_rejected(service: TokenService) -> None:
    issued = service.issue_access_token(USER_ID, Role.ADMIN, now=utcnow() - timedelta(hours=1))
    with pytest.raises(TokenError, match="expired"):
        service.decode_access_token(issued.token)


def test_expiry_honours_leeway(service: TokenService) -> None:
    now = int(utcnow().timestamp())
    token = _encode(_claims(iat=now - 400, nbf=now - 400, exp=now - 10))  # within 30s leeway
    assert service.decode_access_token(token).subject == USER_ID


@pytest.mark.parametrize(
    ("token_factory", "reason"),
    [
        (lambda: _encode(_claims(aud="another-audience")), "verification failed"),
        (lambda: _encode(_claims(iss="https://evil.example")), "verification failed"),
        (lambda: _encode(_claims(), key="a-different-signing-key-" + "z" * 40), "verification failed"),
        (lambda: _encode(_claims(), kid="unknown"), "unknown signing key"),
        (lambda: _encode(_claims(), kid=None), "unknown signing key"),
        (lambda: _encode(_claims(), alg="HS512", key=TEST_SECRET * 2), "algorithm"),
        (lambda: jwt.encode(_claims(), key=None, algorithm="none", headers={"kid": "test-k1"}), "algorithm"),
        (lambda: _encode(_claims(token_use="refresh")), "not an access token"),
        (lambda: _encode(_claims(token_use=None)), "not an access token"),
        (lambda: _encode(_claims(roles=["SUPERUSER"])), "invalid token claims"),
        (lambda: _encode(_claims(roles=[])), "invalid token claims"),
        (lambda: _encode(_claims(roles="ADMIN")), "invalid token claims"),
        (lambda: _encode(_claims(sub="not-a-uuid")), "invalid token claims"),
        (lambda: _encode(_claims(exp=None)), "verification failed"),
        (lambda: _encode(_claims(jti=None)), "verification failed"),
        (lambda: _encode(_claims(nbf=int(utcnow().timestamp()) + 600)), "verification failed"),
        (lambda: "not.a.jwt", "malformed"),
        (lambda: "", "malformed"),
    ],
)
def test_untrusted_tokens_rejected(service: TokenService, token_factory, reason: str) -> None:
    with pytest.raises(TokenError, match=reason):
        service.decode_access_token(token_factory())


def test_tampered_payload_rejected(service: TokenService) -> None:
    header, _, signature = service.issue_access_token(USER_ID, Role.READ_ONLY).token.split(".")
    forged_payload = jwt.utils.base64url_encode(
        jwt.api_jws.json.dumps(_claims(roles=["ADMIN"])).encode()
    ).decode()
    with pytest.raises(TokenError):
        service.decode_access_token(f"{header}.{forged_payload}.{signature}")


def test_key_rotation_accepts_previous_key() -> None:
    old_secret = "previous-signing-key-" + "p" * 40
    old_service = TokenService(make_settings(jwt_key_id="k0", jwt_secret_key=old_secret))
    old_token = old_service.issue_access_token(USER_ID, Role.DOCTOR).token

    rotated = TokenService(make_settings(jwt_key_id="k1", jwt_previous_keys={"k0": old_secret}))
    assert rotated.decode_access_token(old_token).subject == USER_ID
    new_token = rotated.issue_access_token(USER_ID, Role.DOCTOR).token
    assert jwt.get_unverified_header(new_token)["kid"] == "k1"

    retired = TokenService(make_settings(jwt_key_id="k1"))
    with pytest.raises(TokenError, match="unknown signing key"):
        retired.decode_access_token(old_token)
