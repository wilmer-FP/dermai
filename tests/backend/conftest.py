from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.main import app
from app.models import Base

from db_utils import make_sqlite_engine


def make_test_settings() -> Settings:
    """Configuración aislada: no lee el archivo .env local."""
    return Settings(_env_file=None, app_env="testing")


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = make_test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------- API con base de datos SQLite y almacenamiento temporal ----------


@pytest.fixture
def storage_dir(tmp_path: Path) -> Path:
    return tmp_path / "storage"


@pytest.fixture
def db_sessionmaker() -> Iterator[sessionmaker[Session]]:
    engine = make_sqlite_engine()
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def api_client(storage_dir: Path, db_sessionmaker) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None, app_env="testing", storage_path=storage_dir, max_upload_size_mb=1
    )

    def override_get_db() -> Iterator[Session]:
        with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_image_bytes(fmt: str = "PNG", size: tuple[int, int] = (32, 24)) -> bytes:
    buffer = BytesIO()
    PILImage.new("RGB", size, color=(180, 60, 60)).save(buffer, format=fmt)
    return buffer.getvalue()
