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


def facility_payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "code": f"FAC-{uuid.uuid4().hex[:6].upper()}",
        "name": "Northwind General Hospital",
        "facility_type": "HOSPITAL",
        "address_line1": "100 Example Avenue",
        "address_line2": "Block B",
        "city": "Sampleton",
        "state_province": "Demo State",
        "postal_code": "560001",
        "country_code": "IN",
        "main_phone": "+91 80 5550 0100",
        "timezone": "Asia/Kolkata",
    }
    body.update(overrides)
    return body


@pytest.fixture
def create_facility(client: TestClient, admin: dict[str, str]) -> Callable[..., dict[str, Any]]:
    def factory(**overrides: Any) -> dict[str, Any]:
        response = client.post("/api/v1/facilities", json=facility_payload(**overrides), headers=admin)
        assert response.status_code == 201, response.text
        return response.json()

    return factory


@pytest.fixture
def create_department(client: TestClient, admin: dict[str, str]) -> Callable[..., dict[str, Any]]:
    def factory(facility_id: str, code: str = "CARDIO", **overrides: Any) -> dict[str, Any]:
        body = {"code": code, "name": "Cardiology", "floor": "3", "phone_extension": "2101", **overrides}
        response = client.post(f"/api/v1/facilities/{facility_id}/departments", json=body, headers=admin)
        assert response.status_code == 201, response.text
        return response.json()

    return factory


@pytest.fixture
def create_room(client: TestClient, admin: dict[str, str]) -> Callable[..., dict[str, Any]]:
    def factory(
        department_id: str, room_number: str = "3A-01", room_type: str = "CONSULTATION"
    ) -> dict[str, Any]:
        body = {"room_number": room_number, "room_type": room_type}
        response = client.post(f"/api/v1/departments/{department_id}/rooms", json=body, headers=admin)
        assert response.status_code == 201, response.text
        return response.json()

    return factory


@pytest.fixture
def department(create_facility, create_department) -> dict[str, Any]:
    return create_department(create_facility()["id"])
