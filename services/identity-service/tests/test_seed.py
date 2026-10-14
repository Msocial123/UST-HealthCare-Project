import pytest
from sqlalchemy import select

from app import cli
from app.core.passwords import verify_password
from app.models.user import User
from app.services.seed_service import DEMO_ACCOUNTS, seed_demo_users
from tests.conftest import make_settings

DEMO_PASSWORD = "Demo-Only-Placeholder-1"


def test_seed_creates_one_account_per_role(db_session) -> None:
    results = seed_demo_users(db_session, DEMO_PASSWORD)
    assert [r.created for r in results] == [True] * len(DEMO_ACCOUNTS)

    users = db_session.scalars(select(User)).all()
    assert {u.role for u in users} == {"ADMIN", "RECEPTIONIST", "DOCTOR", "READ_ONLY"}
    assert all(u.email.endswith("@demo.smarthospital.example") for u in users)
    assert all(verify_password(u.password_hash, DEMO_PASSWORD) for u in users)
    assert all(DEMO_PASSWORD not in u.password_hash for u in users)


def test_seed_is_idempotent(db_session) -> None:
    seed_demo_users(db_session, DEMO_PASSWORD)
    second = seed_demo_users(db_session, "A-Different-Password-2")
    assert [r.created for r in second] == [False] * len(DEMO_ACCOUNTS)
    assert len(db_session.scalars(select(User)).all()) == len(DEMO_ACCOUNTS)
    admin = db_session.scalar(select(User).where(User.role == "ADMIN"))
    assert verify_password(admin.password_hash, DEMO_PASSWORD)


def test_seed_rejects_weak_password(db_session) -> None:
    with pytest.raises(ValueError, match="at least 12"):
        seed_demo_users(db_session, "short")


def test_seeded_admin_can_login(client, db_session) -> None:
    seed_demo_users(db_session, DEMO_PASSWORD)
    response = client.post(
        "/api/v1/auth/login", json={"email": "admin@demo.smarthospital.example", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200


def test_cli_refuses_production(capsys) -> None:
    settings = make_settings(app_env="production", seed_demo_password=DEMO_PASSWORD)
    assert cli.run_seed(settings) == 2
    assert "production" in capsys.readouterr().err


def test_cli_requires_seed_password(capsys) -> None:
    assert cli.run_seed(make_settings(seed_demo_password=None)) == 2
    assert "SEED_DEMO_PASSWORD" in capsys.readouterr().err


def test_cli_seeds_file_database(tmp_path, capsys) -> None:
    from sqlalchemy import create_engine

    from app.db.base import Base

    url = f"sqlite+pysqlite:///{tmp_path / 'seed.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()

    assert cli.run_seed(make_settings(database_url=url, seed_demo_password=DEMO_PASSWORD)) == 0
    output = capsys.readouterr().out
    assert output.count("created") == len(DEMO_ACCOUNTS)
    assert DEMO_PASSWORD not in output
