"""Shared fixtures. All data is synthetic; no external services are required.

Access tokens are minted here with a test-only secret, following the identity-service token contract.
Set TEST_DATABASE_URL (e.g. a disposable PostgreSQL database) to run the suite against PostgreSQL;
otherwise an in-memory SQLite database is used.
"""

import os
import uuid
from collections.abc import Callable, Iterator
from datetime import date

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time import utcnow
from app.db.base import Base
from app.domain.patients import Sex, generate_mrn
from app.domain.roles import Role
from app.main import create_app
from app.models.patient import Patient

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


def token_claims(roles: list[str] | None = None, **overrides: object) -> dict:
    """Claims shaped like an identity-service access token. Pass a claim as None to omit it."""
    now = int(utcnow().timestamp())
    claims: dict[str, object] = {
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
        "sub": str(uuid.uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + 900,
        "jti": str(uuid.uuid4()),
        "token_use": "access",
        "roles": roles if roles is not None else [Role.ADMIN.value],
    }
    claims.update(overrides)
    return {key: value for key, value in claims.items() if value is not None}


def mint_token(
    roles: list[str] | None = None,
    *,
    key: str = TEST_SECRET,
    kid: str | None = TEST_KEY_ID,
    alg: str = "HS256",
    **claim_overrides: object,
) -> str:
    headers = {"kid": kid, "typ": "JWT"} if kid is not None else {"typ": "JWT"}
    return jwt.encode(token_claims(roles, **claim_overrides), key, algorithm=alg, headers=headers)


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
def db_session(app: FastAPI) -> Iterator[Session]:
    session: Session = app.state.session_factory()
    yield session
    session.close()


@pytest.fixture
def auth_headers() -> Callable[..., dict[str, str]]:
    def factory(*roles: Role) -> dict[str, str]:
        return bearer(mint_token([role.value for role in roles or (Role.ADMIN,)]))

    return factory


@pytest.fixture
def make_patient(db_session: Session) -> Callable[..., Patient]:
    def factory(
        *,
        first_name: str = "Avery",
        last_name: str = "Testpatient",
        date_of_birth: date = date(1990, 4, 12),
        sex: Sex = Sex.UNKNOWN,
        is_active: bool = True,
        **extra: object,
    ) -> Patient:
        patient = Patient(
            medical_record_number=generate_mrn(),
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            sex=sex.value,
            is_active=is_active,
            **extra,
        )
        db_session.add(patient)
        db_session.commit()
        return patient

    return factory
