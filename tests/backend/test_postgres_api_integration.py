"""
Flujo completo de la API contra el PostgreSQL de desarrollo (docker-compose).

Todo ocurre dentro de una transacción que se revierte al final, y los archivos van a una
carpeta temporal: la prueba no deja datos ni archivos. Se omite si PostgreSQL no está disponible.
"""

from collections.abc import Iterator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from PIL import ImageDraw
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.main import app
from app.models import ModelVersion

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
def pg_sessionmaker(pg_engine) -> Iterator[sessionmaker[Session]]:
    connection = pg_engine.connect()
    transaction = connection.begin()
    # Cada commit de la aplicación se convierte en un savepoint dentro de la transacción externa.
    factory = sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False
    )
    yield factory
    transaction.rollback()
    connection.close()


@pytest.fixture
def pg_client(pg_sessionmaker, tmp_path) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, app_env="testing", storage_path=tmp_path, ai_device="cpu")

    def override_get_db() -> Iterator[Session]:
        with pg_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def wound_png() -> bytes:
    image = PILImage.new("RGB", (640, 480), (215, 170, 150))
    draw = ImageDraw.Draw(image)
    draw.ellipse((120, 100, 520, 380), fill=(190, 70, 70))
    draw.ellipse((220, 170, 420, 310), fill=(35, 30, 25))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_full_heuristic_flow_on_postgres(pg_client, tmp_path):
    image = pg_client.post("/api/v1/images", files={"file": ("herida.png", wound_png(), "image/png")})
    assert image.status_code == 201
    image_id = image.json()["id"]

    analysis = pg_client.post(f"/api/v1/images/{image_id}/analyses").json()
    assert analysis["status"] == "completed"
    assert analysis["necrotic_area_ratio"] == pytest.approx(0.25, abs=0.03)
    assert analysis["completed_at"].endswith(("Z", "+00:00"))  # fechas con zona horaria

    # El resultado JSON (JSONB en PostgreSQL) se recupera intacto.
    stored = pg_client.get(f"/api/v1/analyses/{analysis['id']}").json()
    assert stored["result"] == analysis["result"]
    assert stored["status"] == "completed"  # enum nativo analysis_status

    history = pg_client.get("/api/v1/analyses", params={"status": "completed"}).json()
    assert analysis["id"] in [item["id"] for item in history["items"]]
    assert pg_client.get(f"/api/v1/analyses/{analysis['id']}/processed-image").status_code == 200

    assert pg_client.delete(f"/api/v1/images/{image_id}").status_code == 204
    assert pg_client.get(f"/api/v1/analyses/{analysis['id']}").status_code == 404  # ON DELETE CASCADE
    assert list((tmp_path / "images").iterdir()) == []


def test_model_flow_on_postgres(pg_client, pg_sessionmaker, tmp_path):
    torch = pytest.importorskip("torch")
    from ai.models.classes import WOUNDTISSUE_CLASSES
    from ai.models.inference import save_checkpoint
    from ai.models.unet import UNetResNet18

    torch.manual_seed(0)
    weights = tmp_path / "modelo.pt"
    meta = {
        "name": "integration-model",
        "version": "0.0.1",
        "classes": [c.key for c in WOUNDTISSUE_CLASSES],
        "input_size": 64,
        "training_images": 13,
    }
    save_checkpoint(weights, UNetResNet18(num_classes=7), meta)
    with pg_sessionmaker() as session:
        model = ModelVersion(name="integration-model", version="0.0.1", weights_path=str(weights), is_active=True)
        session.add(model)
        session.commit()
        model_id = str(model.id)

    assert model_id in [m["id"] for m in pg_client.get("/api/v1/model-versions", params={"active_only": True}).json()]
    image_id = pg_client.post("/api/v1/images", files={"file": ("herida.png", wound_png(), "image/png")}).json()["id"]

    analysis = pg_client.post(f"/api/v1/images/{image_id}/analyses", json={"model_version_id": model_id}).json()

    assert analysis["status"] == "completed", analysis["error_message"]
    assert analysis["model_version_id"] == model_id
    assert 0 <= analysis["confidence"] <= 1
    assert analysis["result"]["method"]["type"] == "model"
