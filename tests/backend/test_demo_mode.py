"""Modo demo (despliegue público): sesiones aisladas, límite de peticiones y borrado automático."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update

from app import main as app_main
from app.api import deps
from app.core.config import Settings, get_settings
from app.core.database import get_db, make_engine
from app.main import app
from app.models import Analysis, Image
from app.services.demo import RateLimiter, purge_expired_images
from app.services.storage import LocalStorage

from conftest import make_image_bytes

SESSION_A = "aaaaaaaa-1111-4111-8111-111111111111"
SESSION_B = "bbbbbbbb-2222-4222-8222-222222222222"


@pytest.fixture
def demo_settings(storage_dir) -> Settings:
    return Settings(
        _env_file=None,
        app_env="testing",
        storage_path=storage_dir,
        demo_mode=True,
        demo_retention_hours=6,
        demo_rate_limit_per_hour=5,
        frontend_url="https://ejemplo.github.io/dermai/",
    )


@pytest.fixture
def demo_client(demo_settings, db_sessionmaker) -> Iterator[TestClient]:
    def override_get_db():
        with db_sessionmaker() as session:
            yield session

    deps.get_rate_limiter.cache_clear()
    app.dependency_overrides[get_settings] = lambda: demo_settings
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    deps.get_rate_limiter.cache_clear()


def as_session(session_id: str) -> dict[str, str]:
    return {deps.SESSION_HEADER: session_id}


def upload(client: TestClient, session_id: str) -> str:
    response = client.post(
        "/api/v1/images",
        files={"file": ("lesion.png", make_image_bytes(), "image/png")},
        headers=as_session(session_id),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ---------- Sesiones ----------


@pytest.mark.parametrize("headers", [{}, {deps.SESSION_HEADER: "corta"}, {deps.SESSION_HEADER: "x" * 65}])
def test_demo_requires_a_valid_session(demo_client, headers):
    response = demo_client.get("/api/v1/images", headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Falta un identificador de sesión válido (modo demo)."}


def test_each_session_only_sees_its_own_images_and_analyses(demo_client):
    image_id = upload(demo_client, SESSION_A)
    analysis_id = demo_client.post(f"/api/v1/images/{image_id}/analyses", headers=as_session(SESSION_A)).json()["id"]

    owner, other = as_session(SESSION_A), as_session(SESSION_B)
    assert demo_client.get("/api/v1/images", headers=owner).json()["total"] == 1
    assert demo_client.get("/api/v1/analyses", headers=owner).json()["total"] == 1

    assert demo_client.get("/api/v1/images", headers=other).json()["total"] == 0
    assert demo_client.get("/api/v1/analyses", headers=other).json()["total"] == 0
    for path in (
        f"/api/v1/images/{image_id}",
        f"/api/v1/images/{image_id}/file",
        f"/api/v1/images/{image_id}/analyses",
        f"/api/v1/analyses/{analysis_id}",
        f"/api/v1/analyses/{analysis_id}/processed-image",
    ):
        assert demo_client.get(path, headers=other).status_code == 404, path
    assert demo_client.post(f"/api/v1/images/{image_id}/analyses", headers=other).status_code == 404
    assert demo_client.delete(f"/api/v1/images/{image_id}", headers=other).status_code == 404

    # La imagen sigue intacta para su dueño.
    assert demo_client.get(f"/api/v1/images/{image_id}", headers=owner).status_code == 200


def test_files_can_be_requested_with_the_session_in_the_query(demo_client):
    """<img src> no envía cabeceras: la sesión también se acepta como parámetro."""
    image_id = upload(demo_client, SESSION_A)
    analysis_id = demo_client.post(f"/api/v1/images/{image_id}/analyses", headers=as_session(SESSION_A)).json()["id"]

    assert demo_client.get(f"/api/v1/images/{image_id}/file?session={SESSION_A}").status_code == 200
    assert demo_client.get(f"/api/v1/analyses/{analysis_id}/processed-image?session={SESSION_A}").status_code == 200
    assert demo_client.get(f"/api/v1/images/{image_id}/file?session={SESSION_B}").status_code == 404


def test_model_versions_and_health_do_not_need_a_session(demo_client):
    assert demo_client.get("/api/v1/model-versions").status_code == 200
    health = demo_client.get("/api/v1/health").json()
    assert health["demo_mode"] is True
    assert health["demo_retention_hours"] == 6


# ---------- Límite de peticiones ----------


def test_uploads_and_analyses_are_rate_limited(demo_client):
    image_id = upload(demo_client, SESSION_A)  # 1
    for _ in range(4):  # 2..5
        assert demo_client.post(f"/api/v1/images/{image_id}/analyses", headers=as_session(SESSION_A)).status_code == 201

    blocked = demo_client.post(
        "/api/v1/images", files={"file": ("x.png", make_image_bytes(), "image/png")}, headers=as_session(SESSION_B)
    )
    assert blocked.status_code == 429  # el límite es por IP, no por sesión
    assert "5 operaciones por hora" in blocked.json()["detail"]
    # Las consultas no cuentan para el límite.
    assert demo_client.get("/api/v1/images", headers=as_session(SESSION_A)).status_code == 200


def test_rate_limiter_window_expires():
    limiter = RateLimiter(limit=2, window_seconds=10)
    assert limiter.hit("ip", now=0) and limiter.hit("ip", now=1)
    assert not limiter.hit("ip", now=5)
    assert limiter.hit("otra-ip", now=5)
    assert limiter.hit("ip", now=10.5)  # el primer evento ya salió de la ventana


# ---------- Borrado automático ----------


def test_expired_images_are_purged_with_their_files(demo_client, db_sessionmaker, storage_dir):
    old_id = upload(demo_client, SESSION_A)
    demo_client.post(f"/api/v1/images/{old_id}/analyses", headers=as_session(SESSION_A))
    recent_id = upload(demo_client, SESSION_A)
    with db_sessionmaker() as session:
        old = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=7)
        session.execute(update(Image).where(Image.id == uuid.UUID(old_id)).values(created_at=old))
        session.commit()

    with db_sessionmaker() as session:
        removed = purge_expired_images(session, LocalStorage(storage_dir), retention_hours=6)

    assert removed == 1
    with db_sessionmaker() as session:
        assert [str(i) for i in session.scalars(select(Image.id)).all()] == [recent_id]
        assert session.scalars(select(Analysis)).all() == []
    assert len(list((storage_dir / "images").iterdir())) == 1  # solo queda el archivo reciente


def test_purge_once_uses_the_configured_database(monkeypatch, demo_settings, db_sessionmaker):
    monkeypatch.setattr(app_main, "get_sessionmaker", lambda: db_sessionmaker)
    assert app_main.purge_once(demo_settings) == 0


# ---------- Raíz y base de datos ----------


def test_root_describes_the_api(demo_client):
    body = demo_client.get("/").json()
    assert body["docs"] == "/docs"
    assert body["demo_mode"] is True
    assert body["frontend"] == "https://ejemplo.github.io/dermai/"
    assert "No es una herramienta de diagnóstico médico" in body["disclaimer"]


def test_sqlite_engine_enables_foreign_keys(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
    engine.dispose()
