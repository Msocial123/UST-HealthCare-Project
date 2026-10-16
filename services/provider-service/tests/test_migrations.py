from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db.base import Base

SERVICE_ROOT = Path(__file__).resolve().parents[1]
TABLES = {"specialties", "providers", "provider_specialties"}


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
    assert {c["name"] for c in inspector.get_columns("provider_specialties")} == {
        "provider_id",
        "specialty_id",
        "is_primary",
        "created_at",
    }
    unique_indexes = {i["name"] for i in inspector.get_indexes("provider_specialties") if i["unique"]}
    assert "uq_provider_specialties_one_primary" in unique_indexes
    provider_uniques = {tuple(u["column_names"]) for u in inspector.get_unique_constraints("providers")}
    assert {("provider_number",), ("license_number",)} <= provider_uniques

    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == [], f"models and migrations differ: {diff}"

    command.downgrade(config, "base")
    assert not TABLES & set(inspect(engine).get_table_names())
    engine.dispose()
