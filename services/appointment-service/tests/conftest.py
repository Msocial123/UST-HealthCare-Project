"""Shared fixtures. All data is synthetic; no external services are required.

Set TEST_DATABASE_URL (a disposable PostgreSQL database) to run the suite against PostgreSQL; otherwise an
in-memory SQLite database is used. Tokens are minted here with a test-only secret, mirroring the Identity
service token contract. The Scheduling service is replaced by an in-memory fake (SchedulingClient contract).
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
ALL_ROLES = ["ADMIN", "RECEPTIONIST", "DOCTOR", "READ_ONLY"]
FIXED_NOW = datetime(2030, 1, 15, 8, 0, tzinfo=UTC)
IS_POSTGRESQL = os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql")


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        "jwt_secret_key": TEST_SECRET,
        "jwt_issuer": TEST_ISSUER,
        "jwt_audience": TEST_AUDIENCE,
        "jwt_key_id": TEST_KEY_ID,
        "appointments_enabled": True,
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


def at(day: int, hour: int, minute: int = 0) -> str:
    """ISO-8601 UTC instant in March 2030 (after FIXED_NOW)."""
    return datetime(2030, 3, day, hour, minute, tzinfo=UTC).isoformat().replace("+00:00", "Z")


class FakeSchedulingClient:
    """In-memory SchedulingClient used instead of the Scheduling service."""

    def __init__(self) -> None:
        self.available = True
        self.calls: list[tuple[uuid.UUID, uuid.UUID, str]] = []

    def is_available(self, provider_id, facility_id, starts_at, ends_at, access_token) -> bool:
        self.calls.append((provider_id, facility_id, access_token))
        return self.available


def build_app(settings: Settings, **kwargs: Any) -> FastAPI:
    application = create_app(settings, **kwargs)
    application.state.clock = lambda: FIXED_NOW
    engine = application.state.engine
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return application


def teardown_app(application: FastAPI) -> None:
    Base.metadata.drop_all(application.state.engine)
    application.state.engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    application = build_app(settings)
    yield application
    teardown_app(application)


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


def booking_payload(provider_id: str, /, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "patient_id": str(uuid.uuid4()),
        "provider_id": provider_id,
        "facility_id": str(uuid.uuid4()),
        "starts_at": at(4, 9),
        "ends_at": at(4, 9, 30),
        "reason_code": "follow_up",
    }
    body.update(overrides)
    return body


@pytest.fixture
def book(client: TestClient, admin: dict[str, str]) -> Callable[..., dict[str, Any]]:
    def factory(provider_id: str, **overrides: Any) -> dict[str, Any]:
        response = client.post(
            "/api/v1/appointments", json=booking_payload(provider_id, **overrides), headers=admin
        )
        assert response.status_code == 201, response.text
        return response.json()

    return factory
