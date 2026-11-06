"""Casos límite: base de datos no configurada, fallos al guardar y seguridad del almacenamiento."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core import database
from app.core.config import Settings, get_settings
from app.main import app
from app.services import image_service
from app.services.storage import LocalStorage

from conftest import make_image_bytes


@pytest.fixture
def unconfigured_database(monkeypatch):
    """La aplicación sin DATABASE_URL, usando el código real de conexión (sin dobles de get_db)."""
    settings = Settings(_env_file=None, app_env="testing", database_url=None)
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    database.get_engine.cache_clear()
    database.get_sessionmaker.cache_clear()
    app.dependency_overrides[get_settings] = lambda: settings
    yield
    app.dependency_overrides.clear()
    database.get_engine.cache_clear()
    database.get_sessionmaker.cache_clear()


def test_endpoints_return_503_without_database(unconfigured_database):
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200  # no necesita base de datos
        response = client.get("/api/v1/images")

    assert response.status_code == 503
    assert response.json() == {"detail": "La base de datos no está configurada."}


def test_get_engine_explains_missing_url(unconfigured_database):
    with pytest.raises(database.DatabaseNotConfiguredError, match="DATABASE_URL"):
        database.get_engine()


def test_failed_commit_removes_the_stored_file(db_sessionmaker, tmp_path, monkeypatch):
    storage = LocalStorage(tmp_path)
    settings = Settings(_env_file=None, app_env="testing", storage_path=tmp_path)

    with db_sessionmaker() as session:
        def broken_commit():
            raise SQLAlchemyError("fallo simulado")

        monkeypatch.setattr(session, "commit", broken_commit)
        with pytest.raises(SQLAlchemyError):
            image_service.create_image(session, storage, settings, "lesion.png", make_image_bytes())

    assert list(storage.images_dir.iterdir()) == []


@pytest.mark.parametrize(
    "filename", ["../secreto.txt", "..\\secreto.txt", "sub/archivo.png", "sub\\archivo.png", "/etc/passwd", "..", ""]
)
def test_storage_rejects_paths_outside_its_folder(tmp_path, filename):
    storage = LocalStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.path_for(filename)


def test_uploaded_filename_cannot_escape_storage(api_client, storage_dir):
    response = api_client.post(
        "/api/v1/images", files={"file": ("../../fuera.png", make_image_bytes(), "image/png")}
    )

    assert response.status_code == 201
    assert response.json()["original_filename"] == "fuera.png"
    stored = list((storage_dir / "images").iterdir())
    assert len(stored) == 1 and stored[0].parent == storage_dir / "images"
