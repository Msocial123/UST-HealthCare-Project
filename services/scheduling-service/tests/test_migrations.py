from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db.base import Base

SERVICE_ROOT = Path(__file__).resolve().parents[1]
TABLES = {"working_hours", "availability_exceptions"}


def _alembic_config(url: str) -> Config:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    return config


def test_migrations_upgrade_and_downgrade(tmp_path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'migrations.db'}"
    config = _alembic_config(url)

    command.upgrade(config, "head")
    engine = create_engine(url)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) - {"alembic_version"} == TABLES

    # Provider and Facility are referenced by ID only: no cross-service foreign keys.
    for table in TABLES:
        assert inspector.get_foreign_keys(table) == []
    checks = {table: {c["name"] for c in inspector.get_check_constraints(table)} for table in TABLES}
    assert "ck_working_hours_end_after_start" in checks["working_hours"]
    assert "ck_working_hours_slot_minutes_range" in checks["working_hours"]
    assert "ck_availability_exceptions_type_allowed" in checks["availability_exceptions"]

    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == [], f"models and migrations differ: {diff}"

    command.downgrade(config, "base")
    assert not TABLES & set(inspect(engine).get_table_names())
    engine.dispose()
