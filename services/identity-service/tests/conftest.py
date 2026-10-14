"""Shared fixtures. All data is synthetic; no external services are required.

Set TEST_DATABASE_URL (e.g. a disposable PostgreSQL database) to run the suite against PostgreSQL;
otherwise an in-memory SQLite database is used.
"""

import os
import uuid
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.passwords import hash_password
from app.db.base import Base
from app.domain.roles import Role
from app.main import create_app
from app.models.user import User

TEST_SECRET = "unit-test-signing-key-" + "k" * 48  # synthetic, test-only
TEST_ISSUER = "https://identity.unit-test.local"
TEST_AUDIENCE = "smart-hospital-api"
DEFAULT_PASSWORD = "Synthetic-Passw0rd-123"


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        "jwt_secret_key": TEST_SECRET,
        "jwt_issuer": TEST_ISSUER,
        "jwt_audience": TEST_AUDIENCE,
        "jwt_key_id": "test-k1",
        "log_level": "INFO",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


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
def make_user(db_session: Session) -> Callable[..., User]:
    def factory(
        role: Role = Role.READ_ONLY,
        *,
        email: str | None = None,
        password: str = DEFAULT_PASSWORD,
        is_active: bool = True,
        full_name: str = "Synthetic Test User",
    ) -> User:
        user = User(
            email=email or f"user-{uuid.uuid4().hex[:10]}@test.smarthospital.example",
            full_name=full_name,
            role=role.value,
            is_active=is_active,
            password_hash=hash_password(password),
        )
        db_session.add(user)
        db_session.commit()
        return user

    return factory


@pytest.fixture
def token_for(app: FastAPI) -> Callable[[User], str]:
    def factory(user: User) -> str:
        return app.state.token_service.issue_access_token(user.id, Role(user.role)).token

    return factory


@pytest.fixture
def auth_headers(make_user: Callable[..., User], token_for: Callable[[User], str]) -> Callable[..., dict]:
    def factory(role: Role = Role.ADMIN, user: User | None = None) -> dict[str, str]:
        user = user or make_user(role)
        return {"Authorization": f"Bearer {token_for(user)}"}

    return factory
