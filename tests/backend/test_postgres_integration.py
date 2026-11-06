"""
Pruebas de integración contra el PostgreSQL de desarrollo (docker-compose).

Se omiten automáticamente si DATABASE_URL no apunta a PostgreSQL o el servidor
no está disponible. Cada prueba se ejecuta en una transacción que se revierte,
por lo que no deja datos en la base.
"""

from collections.abc import Iterator

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Analysis, AnalysisStatus, Base, Image, ModelVersion

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_engine():
    url = Settings().database_url
    if not url or not url.startswith("postgresql"):
        pytest.skip("DATABASE_URL no apunta a PostgreSQL")
    engine = create_engine(url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL no disponible (¿docker compose up -d?)")
    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine) -> Iterator[Session]:
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def test_schema_is_at_head_and_matches_models(pg_engine):
    with pg_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == "0002"
        assert compare_metadata(context, Base.metadata) == []

    tables = set(inspect(pg_engine).get_table_names())
    assert {"images", "model_versions", "analyses"} <= tables


def test_insert_and_read_back_with_jsonb_and_enum(pg_session):
    model = ModelVersion(name="integration-test", version="0.0.0", metrics={"dice": 0.5})
    image = Image(
        original_filename="test.png",
        stored_filename="integration-test.png",
        content_type="image/png",
        file_size_bytes=100,
        checksum_sha256="b" * 64,
    )
    image.analyses.append(
        Analysis(model_version=model, status=AnalysisStatus.COMPLETED, result={"regions": [1, 2]})
    )
    pg_session.add(image)
    pg_session.flush()

    analysis = pg_session.scalars(select(Analysis).where(Analysis.image_id == image.id)).one()
    assert analysis.status is AnalysisStatus.COMPLETED
    assert analysis.result == {"regions": [1, 2]}
    assert analysis.created_at.tzinfo is not None


def test_check_constraint_is_enforced(pg_session):
    image = Image(
        original_filename="test.png",
        stored_filename="integration-test-ck.png",
        content_type="image/png",
        file_size_bytes=100,
        checksum_sha256="c" * 64,
    )
    image.analyses.append(Analysis(necrotic_area_ratio=2.0))
    pg_session.add(image)

    with pytest.raises(IntegrityError):
        pg_session.flush()
