"""
Pruebas de las migraciones de Alembic.

- Se aplican y revierten sobre SQLite (no requieren servidor PostgreSQL).
- Se comprueba que la migración coincide con los modelos ORM.
- Se genera el SQL para PostgreSQL en modo offline para validar el DDL.
"""

import io
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.models import Base

from db_utils import make_sqlite_engine

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
EXPECTED_TABLES = {"images", "model_versions", "analyses", "alembic_version"}


def make_alembic_config(url: str, output_buffer: io.StringIO | None = None) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"), output_buffer=output_buffer)
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture
def sqlite_engine(tmp_path):
    engine = make_sqlite_engine(f"sqlite+pysqlite:///{tmp_path / 'migrations.db'}")
    yield engine
    engine.dispose()


def run_with_connection(engine, fn, *args) -> None:
    with engine.begin() as connection:
        config = make_alembic_config(str(engine.url))
        config.attributes["connection"] = connection
        fn(config, *args)


def test_upgrade_and_downgrade(sqlite_engine):
    run_with_connection(sqlite_engine, command.upgrade, "head")
    assert set(inspect(sqlite_engine).get_table_names()) == EXPECTED_TABLES

    run_with_connection(sqlite_engine, command.downgrade, "base")
    assert set(inspect(sqlite_engine).get_table_names()) == {"alembic_version"}


def test_session_column_migration_round_trip(sqlite_engine):
    run_with_connection(sqlite_engine, command.upgrade, "head")
    assert "session_id" in {c["name"] for c in inspect(sqlite_engine).get_columns("images")}

    run_with_connection(sqlite_engine, command.downgrade, "0001")
    assert "session_id" not in {c["name"] for c in inspect(sqlite_engine).get_columns("images")}


def test_migrations_match_models(sqlite_engine):
    run_with_connection(sqlite_engine, command.upgrade, "head")

    with sqlite_engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert diff == []


def test_postgresql_offline_sql():
    buffer = io.StringIO()
    config = make_alembic_config("postgresql+psycopg://user:pass@localhost/dermai", buffer)

    command.upgrade(config, "head", sql=True)
    sql = buffer.getvalue()

    assert "CREATE TYPE analysis_status AS ENUM ('pending', 'processing', 'completed', 'failed')" in sql
    assert "CREATE TABLE images" in sql
    assert "CREATE TABLE model_versions" in sql
    assert "CREATE TABLE analyses" in sql
    assert "JSONB" in sql
    assert "ON DELETE CASCADE" in sql
