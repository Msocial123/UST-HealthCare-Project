"""Shared fixtures. All data is synthetic; no external services are required.

Set TEST_DATABASE_URL (e.g. a disposable PostgreSQL database) to run the suite against PostgreSQL;
otherwise an in-memory SQLite database is used. Tokens are minted here with a test-only secret,
mirroring the Identity service token contract.
"""

import os
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.base import Base
from app.main import create_app

TEST_SECRET = "unit-test-signing-key-" + "k" * 48  # synthetic, test-only
TEST_KEY_ID = "test-k1"
TEST_ISSUER = "https://identity.unit-test.local"
TEST_AUDIENCE = "smart-hospital-api"


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        "jwt_secret_key": TEST_SECRET,
        "jwt_issuer": TEST_ISSUER,
        "jwt_audience": TEST_AUDIENCE,
        "jwt_key_id": TEST_KEY_ID,
        "log_level": "INFO",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def mint_token(
    roles: list[str] | None = None,
    *,
    secret: str = TEST_SECRET,
    algorithm: str = "HS256",
    kid: str | None = TEST_KEY_ID,
    lifetime: timedelta = timedelta(minutes=15),
    now: datetime | None = None,
    drop: tuple[str, ...] = (),
    **claims: Any,
) -> str:
    issued_at = now or datetime.now(UTC)
    payload: dict[str, Any] = {
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
        "sub": str(uuid.uuid4()),
        "iat": int(issued_at.timestamp()),
        "nbf": int(issued_at.timestamp()),
        "exp": int((issued_at + lifetime).timestamp()),
        "jti": str(uuid.uuid4()),
        "token_use": "access",
        "roles": roles if roles is not None else ["ADMIN"],
    }
    payload.update(claims)
    for name in drop:
        payload.pop(name, None)
    headers = {"typ": "JWT"}
    if kid is not None:
        headers["kid"] = kid
    return jwt.encode(payload, secret, algorithm=algorithm, headers=headers)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    engine = application.state.engine
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield application
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth() -> Callable[[str], dict[str, str]]:
    def factory(role: str = "ADMIN") -> dict[str, str]:
        return bearer(mint_token([role]))

    return factory


@pytest.fixture
def admin(auth: Callable[[str], dict[str, str]]) -> dict[str, str]:
    return auth("ADMIN")


@pytest.fixture
def create_specialty(client: TestClient, admin: dict[str, str]) -> Callable[..., dict[str, Any]]:
    def factory(code: str = "CARDIOLOGY", name: str | None = None, **extra: Any) -> dict[str, Any]:
        body = {"code": code, "name": name or code.title().replace("_", " "), **extra}
        response = client.post("/api/v1/specialties", json=body, headers=admin)
        assert response.status_code == 201, response.text
        return response.json()

    return factory


def provider_payload(
    specialty_ids: list[str], primary: str | None = None, **overrides: Any
) -> dict[str, Any]:
    primary = primary or specialty_ids[0]
    body: dict[str, Any] = {
        "title": "Dr",
        "first_name": "Avery",
        "last_name": "Testwell",
        "work_email": "avery.testwell@provider.example",
        "work_phone": "+1 555 0100",
        "license_number": f"LIC-{uuid.uuid4().hex[:8].upper()}",
        "years_of_experience": 7,
        "specialties": [{"specialty_id": sid, "is_primary": sid == primary} for sid in specialty_ids],
    }
    body.update(overrides)
    return body


@pytest.fixture
def create_provider(client: TestClient, admin: dict[str, str]) -> Callable[..., dict[str, Any]]:
    def factory(specialty_ids: list[str], primary: str | None = None, **overrides: Any) -> dict[str, Any]:
        response = client.post(
            "/api/v1/providers", json=provider_payload(specialty_ids, primary, **overrides), headers=admin
        )
        assert response.status_code == 201, response.text
        return response.json()

    return factory
