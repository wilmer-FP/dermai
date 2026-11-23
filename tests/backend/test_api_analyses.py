import uuid
from io import BytesIO

import pytest
from PIL import Image as PILImage
from PIL import ImageDraw

from app.core.constants import DISCLAIMER
from app.models import Analysis, AnalysisStatus, ModelVersion
from app.services import processing_service

from conftest import make_image_bytes


def make_wound_png() -> bytes:
    """Lesión sintética: elipse roja con centro negro (25 % del área) sobre piel clara."""
    image = PILImage.new("RGB", (640, 480), (215, 170, 150))
    draw = ImageDraw.Draw(image)
    draw.ellipse((120, 100, 520, 380), fill=(190, 70, 70))
    draw.ellipse((220, 170, 420, 310), fill=(35, 30, 25))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def image_id(api_client) -> str:
    response = api_client.post(
        "/api/v1/images", files={"file": ("lesion.png", make_image_bytes(), "image/png")}
    )
    return response.json()["id"]


@pytest.fixture
def model_version_id(db_sessionmaker) -> str:
    with db_sessionmaker() as session:
        model = ModelVersion(name="necrosis-seg", version="0.1.0", is_active=True, metrics={"dice": 0.7})
        session.add(model)
        session.commit()
        return str(model.id)


def test_create_analysis_runs_pipeline_and_has_disclaimer(api_client, image_id):
    response = api_client.post(f"/api/v1/images/{image_id}/analyses")

    assert response.status_code == 201
    body = response.json()
    assert body["image_id"] == image_id
    assert body["status"] == "completed"
    assert body["model_version_id"] is None
    assert body["necrotic_area_ratio"] == 0
    assert body["confidence"] is None  # el método heurístico no da una probabilidad
    assert body["completed_at"] is not None
    assert body["has_processed_image"] is True
    assert "processed_image_filename" not in body
    assert body["result"]["method"]["name"] == "dermai-opencv-heuristic"
    assert body["disclaimer"] == DISCLAIMER


def test_analysis_of_synthetic_wound_measures_necrotic_area(api_client):
    image_id = api_client.post(
        "/api/v1/images", files={"file": ("herida.png", make_wound_png(), "image/png")}
    ).json()["id"]

    body = api_client.post(f"/api/v1/images/{image_id}/analyses").json()

    assert body["status"] == "completed"
    assert body["necrotic_area_ratio"] == pytest.approx(0.25, abs=0.03)
    assert body["result"]["tissue_composition"]["granulation"] == pytest.approx(0.75, abs=0.05)
    assert body["result"]["segmentation"]["fallback_full_image"] is False


def test_processed_image_endpoint_returns_png(api_client, image_id):
    analysis_id = api_client.post(f"/api/v1/images/{image_id}/analyses").json()["id"]

    response = api_client.get(f"/api/v1/analyses/{analysis_id}/processed-image")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    with PILImage.open(BytesIO(response.content)) as processed:
        assert processed.size == (512, 384)  # lado mayor normalizado


def test_processed_image_of_unknown_analysis_returns_404(api_client):
    response = api_client.get(f"/api/v1/analyses/{uuid.uuid4()}/processed-image")
    assert response.status_code == 404


def test_model_version_without_weights_fails_with_reason(api_client, image_id, model_version_id):
    response = api_client.post(
        f"/api/v1/images/{image_id}/analyses", json={"model_version_id": model_version_id}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["model_version_id"] == model_version_id
    assert body["status"] == "failed"
    assert body["error_message"] == "No se pudo procesar la imagen. La versión de modelo no tiene archivo de pesos."
    assert body["has_processed_image"] is False
    processed = api_client.get(f"/api/v1/analyses/{body['id']}/processed-image")
    assert processed.status_code == 404
    assert processed.json() == {"detail": "El análisis no tiene imagen procesada."}


def test_unreadable_stored_file_marks_analysis_failed(api_client, image_id, storage_dir):
    for path in (storage_dir / "images").iterdir():
        path.write_bytes(b"archivo corrupto")

    body = api_client.post(f"/api/v1/images/{image_id}/analyses").json()

    assert body["status"] == "failed"
    assert body["error_message"].startswith("No se pudo procesar la imagen.")
    assert body["necrotic_area_ratio"] is None
    assert body["has_processed_image"] is False
    assert body["completed_at"] is not None


def test_unexpected_pipeline_error_is_reported_generically(api_client, image_id, monkeypatch):
    def explode(_data):
        raise RuntimeError("detalle interno")

    monkeypatch.setattr(processing_service, "analyze_image_bytes", explode)

    body = api_client.post(f"/api/v1/images/{image_id}/analyses").json()

    assert body["status"] == "failed"
    assert body["error_message"] == "No se pudo procesar la imagen."


def test_create_analysis_with_unknown_model_returns_404(api_client, image_id):
    response = api_client.post(
        f"/api/v1/images/{image_id}/analyses", json={"model_version_id": str(uuid.uuid4())}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Versión de modelo no encontrada."}


def test_create_analysis_for_unknown_image_returns_404(api_client):
    assert api_client.post(f"/api/v1/images/{uuid.uuid4()}/analyses").status_code == 404


def test_list_analyses_of_image(api_client, image_id):
    api_client.post(f"/api/v1/images/{image_id}/analyses")
    api_client.post(f"/api/v1/images/{image_id}/analyses")

    body = api_client.get(f"/api/v1/images/{image_id}/analyses").json()

    assert body["total"] == 2
    assert {a["image_id"] for a in body["items"]} == {image_id}


def test_list_analyses_of_unknown_image_returns_404(api_client):
    assert api_client.get(f"/api/v1/images/{uuid.uuid4()}/analyses").status_code == 404


def test_history_filters_by_status(api_client, image_id, db_sessionmaker):
    api_client.post(f"/api/v1/images/{image_id}/analyses")  # queda `completed`
    with db_sessionmaker() as session:
        session.add(
            Analysis(
                image_id=uuid.UUID(image_id),
                status=AnalysisStatus.FAILED,
                error_message="Imagen ilegible.",
                result={"regions": 2},
            )
        )
        session.commit()

    all_items = api_client.get("/api/v1/analyses").json()
    completed = api_client.get("/api/v1/analyses", params={"status": "completed"}).json()
    failed = api_client.get("/api/v1/analyses", params={"status": "failed"}).json()

    assert all_items["total"] == 2
    assert completed["total"] == 1
    assert failed["total"] == 1
    assert failed["items"][0]["error_message"] == "Imagen ilegible."
    assert failed["items"][0]["result"] == {"regions": 2}


def test_history_rejects_unknown_status(api_client):
    assert api_client.get("/api/v1/analyses", params={"status": "diagnosed"}).status_code == 422


def test_get_analysis(api_client, image_id):
    analysis_id = api_client.post(f"/api/v1/images/{image_id}/analyses").json()["id"]

    response = api_client.get(f"/api/v1/analyses/{analysis_id}")

    assert response.status_code == 200
    assert response.json()["id"] == analysis_id


def test_get_unknown_analysis_returns_404(api_client):
    assert api_client.get(f"/api/v1/analyses/{uuid.uuid4()}").status_code == 404


def test_list_model_versions(api_client, model_version_id, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(ModelVersion(name="baseline", version="0.0.1", is_active=False))
        session.commit()

    all_models = api_client.get("/api/v1/model-versions").json()
    active = api_client.get("/api/v1/model-versions", params={"active_only": True}).json()

    assert len(all_models) == 2
    assert [m["id"] for m in active] == [model_version_id]
    assert "weights_path" not in active[0]
