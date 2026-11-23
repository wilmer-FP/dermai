"""Análisis con modelos de PyTorch y registro de versiones de modelo."""

import json
from io import BytesIO

import pytest
from PIL import Image as PILImage
from sqlalchemy import select

from app.cli import CommandError, main, register_model, set_active, update_metrics
from app.models import ModelVersion

from conftest import make_image_bytes

torch = pytest.importorskip("torch")

from ai.models.classes import WOUNDTISSUE_CLASSES  # noqa: E402
from ai.models.inference import save_checkpoint  # noqa: E402
from ai.models.unet import UNetResNet18  # noqa: E402

META = {
    "name": "test-model",
    "version": "0.0.1",
    "description": "Modelo sin entrenar para pruebas.",
    "architecture": "unet-resnet18",
    "classes": [c.key for c in WOUNDTISSUE_CLASSES],
    "input_size": 64,
    "training_images": 13,
    "run_id": "20261105T000000Z_test",
    "dataset": "sintético",
}


def write_checkpoint(path):
    torch.manual_seed(0)
    save_checkpoint(path, UNetResNet18(num_classes=7), META)
    return path


@pytest.fixture
def image_id(api_client) -> str:
    response = api_client.post(
        "/api/v1/images", files={"file": ("lesion.png", make_image_bytes(size=(96, 64)), "image/png")}
    )
    return response.json()["id"]


def add_model_version(db_sessionmaker, weights_path, **fields) -> str:
    with db_sessionmaker() as session:
        model = ModelVersion(
            name=fields.get("name", "test-model"),
            version=fields.get("version", "0.0.1"),
            weights_path=str(weights_path) if weights_path else None,
            is_active=True,
        )
        session.add(model)
        session.commit()
        return str(model.id)


# ---------- Inferencia desde la API ----------


def test_analysis_with_model_reports_confidence_and_processed_image(api_client, image_id, db_sessionmaker, tmp_path):
    model_id = add_model_version(db_sessionmaker, write_checkpoint(tmp_path / "model.pt"))

    body = api_client.post(f"/api/v1/images/{image_id}/analyses", json={"model_version_id": model_id}).json()

    assert body["status"] == "completed", body["error_message"]
    assert body["model_version_id"] == model_id
    assert 0 <= body["confidence"] <= 1
    assert 0 <= body["necrotic_area_ratio"] <= 1
    assert body["result"]["method"]["type"] == "model"
    assert body["result"]["method"]["name"] == "test-model"
    assert "confidence_definition" in body["result"]
    assert body["has_processed_image"] is True

    processed = api_client.get(f"/api/v1/analyses/{body['id']}/processed-image")
    assert processed.status_code == 200
    with PILImage.open(BytesIO(processed.content)) as image:
        assert image.size == (512, 341)


def test_analysis_with_missing_weights_file_fails(api_client, image_id, db_sessionmaker, tmp_path):
    model_id = add_model_version(db_sessionmaker, tmp_path / "no-existe.pt")

    body = api_client.post(f"/api/v1/images/{image_id}/analyses", json={"model_version_id": model_id}).json()

    assert body["status"] == "failed"
    assert body["error_message"] == "No se pudo procesar la imagen. No se encuentra el archivo de pesos del modelo."


def test_analysis_with_corrupt_weights_fails(api_client, image_id, db_sessionmaker, tmp_path):
    weights = tmp_path / "corrupto.pt"
    weights.write_bytes(b"no es un checkpoint")
    model_id = add_model_version(db_sessionmaker, weights)

    body = api_client.post(f"/api/v1/images/{image_id}/analyses", json={"model_version_id": model_id}).json()

    assert body["status"] == "failed"
    assert body["error_message"] == "No se pudo procesar la imagen. No se pudo cargar el modelo."


def test_heuristic_analysis_still_has_no_confidence(api_client, image_id):
    body = api_client.post(f"/api/v1/images/{image_id}/analyses").json()
    assert body["status"] == "completed"
    assert body["confidence"] is None
    assert body["result"]["legend"][0]["label"] == "Región analizada"


# ---------- Registro de modelos (CLI) ----------


@pytest.fixture
def run_dir(tmp_path):
    run = tmp_path / "runs" / "20261105T000000Z_test"
    run.mkdir(parents=True)
    write_checkpoint(run / "model.pt")
    (run / "model_meta.json").write_text(json.dumps(META), encoding="utf-8")
    metrics = {"summary": {"cv_mean_dice_foreground": 0.42, "training_images": 13}}
    (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    return run


def test_register_model_copies_weights_and_stores_metrics(db_sessionmaker, run_dir, tmp_path):
    weights_dir = tmp_path / "weights"
    with db_sessionmaker() as session:
        model = register_model(session, run_dir, activate=True, weights_dir=weights_dir)

    assert (weights_dir / "test-model-0.0.1.pt").is_file()
    assert model.is_active is True
    assert model.architecture == "unet-resnet18"
    assert model.metrics["cv_mean_dice_foreground"] == 0.42
    assert model.metrics["run_id"] == "20261105T000000Z_test"

    with db_sessionmaker() as session, pytest.raises(CommandError, match="Ya existe"):
        register_model(session, run_dir, weights_dir=weights_dir)


def test_update_metrics_replaces_summary(db_sessionmaker, run_dir, tmp_path):
    with db_sessionmaker() as session:
        register_model(session, run_dir, weights_dir=tmp_path / "weights")
    (run_dir / "metrics.json").write_text(json.dumps({"summary": {"cv_fold_dice_mean": 0.3}}), encoding="utf-8")

    with db_sessionmaker() as session:
        model = update_metrics(session, run_dir)

    assert model.metrics["cv_fold_dice_mean"] == 0.3
    assert "cv_mean_dice_foreground" not in model.metrics


def test_register_model_requires_run_files(db_sessionmaker, tmp_path):
    with db_sessionmaker() as session, pytest.raises(CommandError, match="Falta"):
        register_model(session, tmp_path, weights_dir=tmp_path / "weights")


def test_activating_a_model_deactivates_the_others(db_sessionmaker):
    add_model_version(db_sessionmaker, None, name="a", version="1")
    add_model_version(db_sessionmaker, None, name="b", version="1")

    with db_sessionmaker() as session:
        set_active(session, "a", "1", True)
    with db_sessionmaker() as session:
        active = session.scalars(select(ModelVersion.name).where(ModelVersion.is_active.is_(True))).all()
    assert active == ["a"]


def test_cli_main_reports_errors(db_sessionmaker, capsys):
    code = main(["activate-model", "nada", "0"], session_factory=db_sessionmaker)
    assert code == 1
    assert "No existe la versión" in capsys.readouterr().err


def test_cli_main_registers_model(db_sessionmaker, run_dir, monkeypatch, tmp_path, capsys):
    import app.cli as cli

    # Los pesos se copian a una carpeta temporal en lugar de ai/models/weights.
    original = cli.register_model
    monkeypatch.setattr(
        cli,
        "register_model",
        lambda db, run, activate, **kwargs: original(db, run, activate, tmp_path / "weights", **kwargs),
    )

    assert main(["register-model", str(run_dir), "--activate"], session_factory=db_sessionmaker) == 0
    assert "Registrado test-model 0.0.1" in capsys.readouterr().out
    with db_sessionmaker() as session:
        assert session.scalar(select(ModelVersion.is_active).where(ModelVersion.name == "test-model")) is True
