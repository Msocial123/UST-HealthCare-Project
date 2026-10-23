import os
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.patient import Patient

SERVICE_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COLUMNS = {
    "id",
    "medical_record_number",
    "first_name",
    "last_name",
    "date_of_birth",
    "sex",
    "phone",
    "email",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal_code",
    "country",
    "is_active",
    "created_at",
    "updated_at",
}


def _alembic_config(url: str) -> Config:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    return config


def _index_names(engine) -> set[str]:
    # SQLAlchemy cannot reflect expression indexes on SQLite, so read the catalog directly there.
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            rows = connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'index'"))
        else:
            rows = connection.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = 'patients'"))
        return {row[0] for row in rows}


@pytest.fixture
def migration_url(tmp_path) -> str:
    return os.environ.get("TEST_DATABASE_URL") or f"sqlite+pysqlite:///{tmp_path / 'migrations.db'}"


@pytest.mark.filterwarnings("ignore:Skipped unsupported reflection of expression-based index")
def test_migrations_upgrade_match_models_and_downgrade(migration_url: str) -> None:
    engine = create_engine(migration_url)
    Base.metadata.drop_all(engine)
    config = _alembic_config(migration_url)

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert "patients" in inspector.get_table_names()
    assert {column["name"] for column in inspector.get_columns("patients")} == EXPECTED_COLUMNS
    assert _index_names(engine) >= {
        "ix_patients_last_name_lower",
        "ix_patients_first_name_lower",
        "ix_patients_date_of_birth",
    }
    unique = {
        tuple(constraint["column_names"]) for constraint in inspector.get_unique_constraints("patients")
    }
    assert ("medical_record_number",) in unique

    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []

    command.downgrade(config, "base")
    assert "patients" not in inspect(engine).get_table_names()
    engine.dispose()


@pytest.mark.filterwarnings("ignore:Skipped unsupported reflection of expression-based index")
def test_migrations_downgrade_then_upgrade_round_trip(migration_url: str) -> None:
    engine = create_engine(migration_url)
    Base.metadata.drop_all(engine)
    config = _alembic_config(migration_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    assert "patients" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")

    inspector = inspect(engine)
    assert {column["name"] for column in inspector.get_columns("patients")} == EXPECTED_COLUMNS
    assert _index_names(engine) >= {
        "ix_patients_last_name_lower",
        "ix_patients_first_name_lower",
        "ix_patients_date_of_birth",
    }
    unique = {
        tuple(constraint["column_names"]) for constraint in inspector.get_unique_constraints("patients")
    }
    assert ("medical_record_number",) in unique
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []

    command.downgrade(config, "base")
    engine.dispose()


def test_migrated_schema_rejects_duplicate_mrn(migration_url: str) -> None:
    engine = create_engine(migration_url)
    Base.metadata.drop_all(engine)
    config = _alembic_config(migration_url)
    command.upgrade(config, "head")

    def synthetic_patient() -> Patient:
        return Patient(
            medical_record_number="MRN-DUPLICATE1",
            first_name="Dana",
            last_name="Duplicate-Test",
            date_of_birth=date(1985, 3, 14),
            sex="UNKNOWN",
        )

    try:
        with Session(engine) as session:
            session.add(synthetic_patient())
            session.commit()
            session.add(synthetic_patient())
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            assert session.scalar(select(func.count()).select_from(Patient)) == 1
    finally:
        command.downgrade(config, "base")
        engine.dispose()
