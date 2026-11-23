import json

import numpy as np
import pytest

from ai.evaluation.metrics import area_ratio, confusion_matrix, segmentation_metrics
from ai.models.classes import GROUPS, WOUNDTISSUE_CLASSES, decode_color_mask, group_indices
from ai.models.data import find_samples, read_sample

import synthetic

torch = pytest.importorskip("torch")

from ai.models.inference import analyze_with_model, load_model, save_checkpoint  # noqa: E402
from ai.models.transforms import augment, normalize  # noqa: E402
from ai.models.unet import UNetResNet18  # noqa: E402

CLASS_KEYS = [c.key for c in WOUNDTISSUE_CLASSES]
PALETTE = {c.key: c.mask_color for c in WOUNDTISSUE_CLASSES}


# ---------- Clases y máscaras ----------


def test_decode_color_mask_maps_palette_and_near_colors():
    rgb = np.array([[PALETTE["background"], PALETTE["necrosis"], (250, 5, 3)]], np.uint8)  # rojo casi exacto
    assert decode_color_mask(rgb).tolist() == [[0, 3, 1]]


def test_decode_color_mask_rejects_unknown_colors():
    with pytest.raises(ValueError):
        decode_color_mask(np.array([[(0, 128, 0)]], np.uint8))  # verde: no es ninguna clase


def test_group_indices_merges_rare_classes_into_other():
    labels = np.array([CLASS_KEYS.index(k) for k in ("background", "necrosis", "bone", "tendon", "maceration")])
    assert [GROUPS[g] for g in group_indices(labels)] == ["background", "necrotic", "other", "other", "other"]


# ---------- Métricas ----------


def test_segmentation_metrics_on_known_confusion():
    target = np.array([0, 0, 1, 1, 1, 2])
    prediction = np.array([0, 1, 1, 1, 0, 2])
    metrics = segmentation_metrics(confusion_matrix(prediction, target, 4), ["bg", "a", "b", "absent"])

    a = metrics["per_class"]["a"]
    assert a["iou"] == pytest.approx(2 / 4)  # TP 2, FP 1, FN 1
    assert a["dice"] == pytest.approx(4 / 6)
    assert a["precision"] == pytest.approx(2 / 3)
    assert a["sensitivity"] == pytest.approx(2 / 3)
    assert a["specificity"] == pytest.approx(2 / 3)
    assert metrics["per_class"]["absent"]["iou"] is None
    assert metrics["pixel_accuracy"] == pytest.approx(4 / 6)
    # Medias solo sobre clases presentes; la versión "foreground" excluye la primera.
    assert metrics["mean_dice_foreground"] == pytest.approx((4 / 6 + 1.0) / 2)


def test_confusion_matrix_requires_same_shape():
    with pytest.raises(ValueError):
        confusion_matrix(np.zeros(3), np.zeros(4), 2)


def test_area_ratio_ignores_background():
    labels = np.array([0, 0, 3, 1, 1, 1])
    assert area_ratio(labels, 3) == pytest.approx(0.25)
    assert area_ratio(np.zeros(4, int), 3) == 0


# ---------- Datos y transformaciones ----------


def test_find_and_read_samples(tmp_path):
    synthetic.write_segmentation_dataset(tmp_path, count=3)
    samples = find_samples(tmp_path)
    assert [s.name for s in samples] == ["img0", "img1", "img2"]

    image, mask = read_sample(samples[0])
    assert image.shape == (64, 64, 3) and image.dtype == np.uint8
    assert set(np.unique(mask)) == {0, 1, 3}


def test_find_samples_reports_missing_mask(tmp_path):
    synthetic.write_segmentation_dataset(tmp_path, count=2)
    (tmp_path / "label" / "img1.png").unlink()
    with pytest.raises(FileNotFoundError, match="img1"):
        find_samples(tmp_path)


def test_augment_is_deterministic_and_keeps_labels():
    image = synthetic.wound()[..., ::-1].copy()
    mask = np.zeros(image.shape[:2], np.int64)
    mask[100:300, 200:400] = 3

    first = augment(image, mask, 128, np.random.default_rng(7))
    second = augment(image, mask, 128, np.random.default_rng(7))
    assert first[0].shape == (128, 128, 3) and first[1].shape == (128, 128)
    assert np.array_equal(first[0], second[0]) and np.array_equal(first[1], second[1])
    assert set(np.unique(first[1])) <= {0, 3}


def test_normalize_returns_chw_float():
    tensor = normalize(np.zeros((10, 12, 3), np.uint8))
    assert tensor.shape == (3, 10, 12) and tensor.dtype == np.float32


# ---------- Modelo ----------


def test_unet_output_matches_input_size():
    model = UNetResNet18(num_classes=7).eval()
    with torch.no_grad():
        logits = model(torch.zeros(1, 3, 100, 75))
    assert logits.shape == (1, 7, 100, 75)


def make_checkpoint(path, training_images=13):
    torch.manual_seed(0)
    meta = {
        "name": "test-model",
        "version": "0.0.1",
        "description": "Modelo sin entrenar para pruebas.",
        "architecture": "unet-resnet18",
        "classes": CLASS_KEYS,
        "input_size": 64,
        "training_images": training_images,
    }
    save_checkpoint(path, UNetResNet18(num_classes=7), meta)
    return path


def test_checkpoint_round_trip_and_inference(tmp_path):
    loaded = load_model(make_checkpoint(tmp_path / "model.pt"), device="cpu")
    output = analyze_with_model(synthetic.wound(), loaded)
    result = json.loads(json.dumps(output.result))

    assert result["method"] == {
        "name": "test-model",
        "version": "0.0.1",
        "type": "model",
        "description": "Modelo sin entrenar para pruebas.",
    }
    assert 0 <= output.confidence <= 1
    assert set(result["tissue_composition"]) == {"necrotic", "slough", "granulation", "other"}
    assert output.necrotic_area_ratio == result["tissue_composition"]["necrotic"]
    assert output.overlay.shape == (384, 512, 3)
    assert any("prueba de concepto" in w for w in result["warnings"])
    assert result["legend"][0]["kind"] == "outline"


# ---------- Entrenamiento ----------


def test_training_run_produces_reproducible_artifacts(tmp_path):
    from ai.experiments.train import PROJECT_ROOT, main

    data_root = tmp_path / "data"
    synthetic.write_segmentation_dataset(data_root, count=4)
    config = PROJECT_ROOT / "ai" / "experiments" / "configs" / "unet_resnet18_woundtissue.json"
    args = [
        "--config",
        str(config),
        "--data-root",
        str(data_root),
        "--output-dir",
        str(tmp_path / "runs"),
        "--epochs",
        "1",
        "--folds",
        "2",
        "--samples-per-image",
        "1",
        "--device",
        "cpu",
        "--no-pretrained",
    ]

    run_dir = main(args)

    expected = {
        "config.json",
        "environment.json",
        "history.csv",
        "metrics.json",
        "model.pt",
        "model_meta.json",
        "model_card.md",
    }
    assert expected <= {p.name for p in run_dir.iterdir()}
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["dataset"]["images"] == 4
    assert metrics["cross_validation"]["folds"] == 2
    assert len(metrics["cross_validation"]["per_image"]) == 4
    assert "heuristic_baseline" in metrics
    assert {"cv_mean_dice_foreground", "cv_necrotic_ratio_mae", "training_images"} <= metrics["summary"].keys()
    environment = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
    assert set(environment["data_files"]) == {"img0", "img1", "img2", "img3"}
    config_saved = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    assert config_saved["pretrained_encoder"] is False and config_saved["epochs"] == 1

    assert {"cv_fold_dice_mean", "cv_fold_dice_std"} <= metrics["summary"].keys()
    assert "por partición" in (run_dir / "model_card.md").read_text(encoding="utf-8")

    loaded = load_model(run_dir / "model.pt", device="cpu")
    assert loaded.meta["training_images"] == 4

    # Los informes se pueden regenerar sin reentrenar.
    (run_dir / "model_card.md").unlink()
    assert main(["--refresh-reports", str(run_dir)]) == run_dir
    assert (run_dir / "model_card.md").is_file()
