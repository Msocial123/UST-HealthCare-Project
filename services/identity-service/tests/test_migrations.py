from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

SERVICE_ROOT = Path(__file__).resolve().parents[1]


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
    assert "users" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("users")}
    assert columns == {
        "id",
        "email",
        "full_name",
        "password_hash",
        "role",
        "is_active",
        "created_at",
        "updated_at",
        "last_login_at",
    }
    assert "password" not in columns

    command.downgrade(config, "base")
    assert "users" not in inspect(engine).get_table_names()
    engine.dispose()
