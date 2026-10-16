"""Shared fixtures. All data is synthetic; no external services are required.

Set TEST_DATABASE_URL (e.g. a disposable PostgreSQL database) to run the suite against PostgreSQL;
otherwise an in-memory SQLite database is used. Tokens are minted here with a test-only secret,
mirroring the Identity service token contract. The Facility service is replaced by an in-memory fake
implementing the FacilityClient contract.
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

from app.clients.facility_client import FACILITY_UNAVAILABLE_MESSAGE, FacilityInfo
from app.core.config import Settings
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.db.base import Base
from app.main import create_app

TEST_SECRET = "unit-test-signing-key-" + "k" * 48  # synthetic, test-only
TEST_KEY_ID = "test-k1"
TEST_ISSUER = "https://identity.unit-test.local"
TEST_AUDIENCE = "smart-hospital-api"
ALL_ROLES = ["ADMIN", "RECEPTIONIST", "DOCTOR", "READ_ONLY"]


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        "jwt_secret_key": TEST_SECRET,
        "jwt_issuer": TEST_ISSUER,
        "jwt_audience": TEST_AUDIENCE,
        "jwt_key_id": TEST_KEY_ID,
        "facility_service_url": "http://facility.unit-test.local",
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


class FakeFacilityClient:
    """In-memory FacilityClient used instead of the Facility service."""

    def __init__(self) -> None:
        self.facilities: dict[uuid.UUID, FacilityInfo] = {}
        self.unavailable = False
        self.calls: list[tuple[uuid.UUID, str]] = []

    def add(self, timezone: str = "Europe/London", *, is_active: bool = True) -> str:
        facility_id = uuid.uuid4()
        self.facilities[facility_id] = FacilityInfo(id=facility_id, timezone=timezone, is_active=is_active)
        return str(facility_id)

    def get_facility(self, facility_id: uuid.UUID, access_token: str) -> FacilityInfo:
        self.calls.append((facility_id, access_token))
        if self.unavailable:
            raise ServiceUnavailableError(FACILITY_UNAVAILABLE_MESSAGE)
        info = self.facilities.get(facility_id)
        if info is None:
            raise NotFoundError("Facility not found")
        return info


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def facilities() -> FakeFacilityClient:
    return FakeFacilityClient()


@pytest.fixture
def app(settings: Settings, facilities: FakeFacilityClient) -> Iterator[FastAPI]:
    application = create_app(settings, facility_client=facilities)
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
def provider_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def facility_id(facilities: FakeFacilityClient) -> str:
    return facilities.add("Europe/London")


def working_hours_payload(facility_id: str, /, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "facility_id": facility_id,
        "weekday": 0,
        "start_local_time": "09:00",
        "end_local_time": "12:00",
        "slot_minutes": 30,
        "valid_from": "2026-01-01",
    }
    body.update(overrides)
    return body


def exception_payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "starts_at": "2026-04-06T09:00:00Z",
        "ends_at": "2026-04-06T10:00:00Z",
        "type": "LEAVE",
        "reason_code": "ANNUAL_LEAVE",
    }
    body.update(overrides)
    return body


@pytest.fixture
def create_working_hours(client: TestClient, admin: dict[str, str]) -> Callable[..., dict[str, Any]]:
    def factory(provider_id: str, facility_id: str, **overrides: Any) -> dict[str, Any]:
        response = client.post(
            f"/api/v1/providers/{provider_id}/working-hours",
            json=working_hours_payload(facility_id, **overrides),
            headers=admin,
        )
        assert response.status_code == 201, response.text
        return response.json()

    return factory


@pytest.fixture
def create_exception(client: TestClient, admin: dict[str, str]) -> Callable[..., dict[str, Any]]:
    def factory(provider_id: str, **overrides: Any) -> dict[str, Any]:
        response = client.post(
            f"/api/v1/providers/{provider_id}/exceptions", json=exception_payload(**overrides), headers=admin
        )
        assert response.status_code == 201, response.text
        return response.json()

    return factory
