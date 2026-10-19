import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.db.base import Base
from tests.conftest import IS_POSTGRESQL

SERVICE_ROOT = Path(__file__).resolve().parents[1]
TABLES = {"appointments", "outbox_events"}


def _alembic_config(url: str) -> Config:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    return config


def _round_trip(url: str) -> None:
    config = _alembic_config(url)
    engine = create_engine(url)
    Base.metadata.drop_all(engine)  # start from an empty schema (test database only)
    try:
        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) >= TABLES

        # Patient, Provider and Facility are referenced by ID only: no cross-service foreign keys.
        for table in TABLES:
            assert inspector.get_foreign_keys(table) == []
        checks = {c["name"] for c in inspector.get_check_constraints("appointments")}
        assert {
            "ck_appointments_ends_after_starts",
            "ck_appointments_status_allowed",
            "ck_appointments_cancellation_reason_iff_cancelled",
        } <= checks

        with engine.connect() as connection:
            diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == [], f"models and migrations differ: {diff}"

        command.downgrade(config, "-1")
        assert not TABLES & set(inspect(engine).get_table_names())
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        assert not TABLES & set(inspect(engine).get_table_names())
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()


def test_migrations_upgrade_and_downgrade_sqlite(tmp_path) -> None:
    _round_trip(f"sqlite+pysqlite:///{tmp_path / 'migrations.db'}")


@pytest.mark.skipif(not IS_POSTGRESQL, reason="needs PostgreSQL via TEST_DATABASE_URL")
def test_migrations_upgrade_and_downgrade_postgresql() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    _round_trip(url)
    engine = create_engine(url)
    try:
        command.upgrade(_alembic_config(url), "head")
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT contype FROM pg_constraint WHERE conname = 'ex_appointments_provider_overlap'")
            ).one()
        assert row.contype == "x"  # exclusion constraint
    finally:
        command.downgrade(_alembic_config(url), "base")
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()
