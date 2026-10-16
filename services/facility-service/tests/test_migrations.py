from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db.base import Base

SERVICE_ROOT = Path(__file__).resolve().parents[1]
TABLES = {"facilities", "departments", "rooms"}


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
    assert set(inspector.get_table_names()) >= TABLES

    uniques = {
        table: {tuple(u["column_names"]) for u in inspector.get_unique_constraints(table)} for table in TABLES
    }
    assert ("code",) in uniques["facilities"]
    assert ("facility_id", "code") in uniques["departments"]
    assert ("department_id", "room_number") in uniques["rooms"]
    foreign_keys = {
        table: {
            (tuple(fk["constrained_columns"]), fk["referred_table"])
            for fk in inspector.get_foreign_keys(table)
        }
        for table in ("departments", "rooms")
    }
    assert foreign_keys["departments"] == {(("facility_id",), "facilities")}
    assert foreign_keys["rooms"] == {(("department_id",), "departments")}

    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == [], f"models and migrations differ: {diff}"

    command.downgrade(config, "base")
    assert not TABLES & set(inspect(engine).get_table_names())
    engine.dispose()
