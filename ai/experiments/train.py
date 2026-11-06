"""Entrenamiento y evaluación reproducibles del modelo de segmentación de tejidos.

Uso (desde la raíz del proyecto):

    .\\backend\\.venv\\Scripts\\python -m ai.experiments.train \\
        --config ai/experiments/configs/unet_resnet18_woundtissue.json

Genera `ai/experiments/runs/<fecha>_<nombre>/` con: configuración, entorno (versiones, GPU y
hashes de los datos), historial de pérdidas, métricas de validación cruzada, comparación con
la heurística de ai/preprocessing, el modelo final (`model.pt`) y su ficha (`model_card.md`).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import random
import sys
import time
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Los pesos preentrenados se guardan dentro del proyecto (no versionados), no en la caché del usuario.
os.environ.setdefault("TORCH_HOME", str(PROJECT_ROOT / "ai" / "models" / "cache"))

import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402
import torchvision  # noqa: E402
from torch.utils.data import DataLoader, Dataset  # noqa: E402

from ai.evaluation.metrics import area_ratio, confusion_matrix, segmentation_metrics  # noqa: E402
from ai.models.classes import GROUPS, WOUNDTISSUE_CLASSES, group_indices  # noqa: E402
from ai.models.data import find_samples, read_sample  # noqa: E402
from ai.models.inference import LoadedModel, predict_probabilities, resolve_device, save_checkpoint  # noqa: E402
from ai.models.transforms import augment, normalize  # noqa: E402
from ai.models.unet import ARCHITECTURE, UNetResNet18  # noqa: E402
from ai.preprocessing import analyze_image  # noqa: E402
from ai.preprocessing import tissue as heuristic_tissue  # noqa: E402

CLASS_KEYS = [c.key for c in WOUNDTISSUE_CLASSES]
NECROSIS_INDEX = CLASS_KEYS.index("necrosis")
NUM_CLASSES = len(WOUNDTISSUE_CLASSES)

# Etiquetas de la heurística -> grupos comunes (background, granulation, slough, necrotic, other).
HEURISTIC_TO_GROUP = {
    heuristic_tissue.EXCLUDED: GROUPS.index("background"),
    heuristic_tissue.NECROTIC: GROUPS.index("necrotic"),
    heuristic_tissue.SLOUGH: GROUPS.index("slough"),
    heuristic_tissue.GRANULATION: GROUPS.index("granulation"),
    heuristic_tissue.OTHER: GROUPS.index("other"),
}


@dataclass
class TrainConfig:
    name: str
    version: str
    description: str = ""
    data_root: str = "ai/datasets/woundtissue/raw/WoundTissue-main"
    pretrained_encoder: bool = True
    input_size: int = 256
    epochs: int = 40
    batch_size: int = 8
    samples_per_image: int = 20
    learning_rate: float = 3e-4
    weight_decay: float = 1e-4
    dice_loss_weight: float = 1.0
    folds: int = 5
    seed: int = 42
    device: str = "auto"
    evaluate_heuristic: bool = True

    @classmethod
    def load(cls, path: Path, overrides: dict[str, Any]) -> TrainConfig:
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"Parámetros desconocidos en la configuración: {sorted(unknown)}")
        data.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**data)


# ---------- Reproducibilidad ----------


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment_info(device: torch.device, samples) -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "cuda": torch.version.cuda,
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "cudnn_deterministic": torch.backends.cudnn.deterministic,
        "data_files": {s.name: {"image": sha256(s.image_path), "mask": sha256(s.mask_path)} for s in samples},
    }


# ---------- Datos ----------


class CropDataset(Dataset):
    """Recortes aumentados; cada imagen aparece `samples_per_image` veces por época."""

    def __init__(self, items: list[tuple[np.ndarray, np.ndarray]], size: int, samples_per_image: int, seed: int):
        self.items = items
        self.size = size
        self.samples_per_image = samples_per_image
        self.seed = seed
        self.epoch = 0

    def __len__(self) -> int:
        return len(self.items) * self.samples_per_image

    def __getitem__(self, index: int):
        rng = np.random.default_rng((self.seed, self.epoch, index))
        image, mask = self.items[index % len(self.items)]
        image, mask = augment(image, mask, self.size, rng)
        return torch.from_numpy(normalize(image)), torch.from_numpy(mask)


def class_weights(items: list[tuple[np.ndarray, np.ndarray]]) -> torch.Tensor:
    """Pesos 1/√frecuencia para las clases presentes (media 1); 0 para las ausentes."""
    counts = np.zeros(NUM_CLASSES, dtype=np.float64)
    for _, mask in items:
        counts += np.bincount(mask.ravel(), minlength=NUM_CLASSES)
    present = counts > 0
    weights = np.zeros(NUM_CLASSES, dtype=np.float64)
    weights[present] = 1.0 / np.sqrt(counts[present] / counts.sum())
    weights[present] /= weights[present].mean()
    return torch.tensor(weights, dtype=torch.float32)


def dice_loss(logits: torch.Tensor, target: torch.Tensor, active: torch.Tensor) -> torch.Tensor:
    probabilities = torch.softmax(logits, dim=1)
    one_hot = F.one_hot(target, NUM_CLASSES).permute(0, 3, 1, 2).float()
    dims = (0, 2, 3)
    intersection = (probabilities * one_hot).sum(dims)
    denominator = probabilities.sum(dims) + one_hot.sum(dims)
    dice = (2 * intersection + 1.0) / (denominator + 1.0)
    return 1.0 - dice[active].mean()


# ---------- Entrenamiento y evaluación ----------


def train_model(
    items: list[tuple[np.ndarray, np.ndarray]],
    config: TrainConfig,
    device: torch.device,
    seed: int,
    history: list[dict[str, Any]],
    stage: str,
) -> torch.nn.Module:
    set_seed(seed)
    model = UNetResNet18(NUM_CLASSES, pretrained_encoder=config.pretrained_encoder).to(device)
    dataset = CropDataset(items, config.input_size, config.samples_per_image, seed)
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(dataset, batch_size=config.batch_size, shuffle=True, generator=generator, num_workers=0)
    weights = class_weights(items).to(device)
    active = weights > 0
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, config.epochs * len(loader)))

    for epoch in range(config.epochs):
        dataset.epoch = epoch
        model.train()
        totals = {"loss": 0.0, "cross_entropy": 0.0, "dice": 0.0}
        batches = 0
        for images, masks in loader:
            images, masks = images.to(device), masks.to(device)
            logits = model(images)
            ce = F.cross_entropy(logits, masks, weight=weights)
            dl = dice_loss(logits, masks, active)
            loss = ce + config.dice_loss_weight * dl
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            scheduler.step()
            totals["loss"] += loss.item()
            totals["cross_entropy"] += ce.item()
            totals["dice"] += dl.item()
            batches += 1
        history.append({"stage": stage, "epoch": epoch + 1, **{k: v / max(1, batches) for k, v in totals.items()}})
    return model.eval()


def predict_labels(
    model: torch.nn.Module, image_rgb: np.ndarray, config: TrainConfig, device: torch.device
) -> np.ndarray:
    loaded = LoadedModel(model, {"input_size": config.input_size, "classes": CLASS_KEYS}, device)
    return predict_probabilities(loaded, image_rgb).argmax(axis=0)


def make_folds(count: int, folds: int, seed: int) -> list[np.ndarray]:
    order = np.random.default_rng(seed).permutation(count)
    return [fold for fold in np.array_split(order, min(folds, count)) if fold.size]


def evaluate_heuristic(items, names) -> dict[str, Any]:
    """Aplica la heurística de ai/preprocessing a las mismas imágenes y la compara con las máscaras."""
    matrix = np.zeros((len(GROUPS), len(GROUPS)), dtype=np.int64)
    per_image = []
    lookup = np.zeros(256, dtype=np.int64)
    for code, group in HEURISTIC_TO_GROUP.items():
        lookup[code] = group
    for (image, mask), name in zip(items, names, strict=True):
        output = analyze_image(cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        labels = cv2.resize(output.tissue_labels, (mask.shape[1], mask.shape[0]), interpolation=cv2.INTER_NEAREST)
        predicted = lookup[labels]
        truth = group_indices(mask)
        matrix += confusion_matrix(predicted, truth, len(GROUPS))
        per_image.append(
            {
                "image": name,
                "true_necrotic_ratio": area_ratio(truth, GROUPS.index("necrotic")),
                "predicted_necrotic_ratio": output.necrotic_area_ratio,
            }
        )
    return {
        "groups": segmentation_metrics(matrix, GROUPS),
        "necrotic_ratio_mae": float(
            np.mean([abs(r["true_necrotic_ratio"] - r["predicted_necrotic_ratio"]) for r in per_image])
        ),
        "per_image": per_image,
    }


def cross_validate(items, names, config: TrainConfig, device: torch.device, history) -> dict[str, Any]:
    matrix_classes = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=np.int64)
    matrix_groups = np.zeros((len(GROUPS), len(GROUPS)), dtype=np.int64)
    per_image, per_fold = [], []

    for fold_index, validation in enumerate(make_folds(len(items), config.folds, config.seed)):
        training = [items[i] for i in range(len(items)) if i not in set(validation.tolist())]
        model = train_model(training, config, device, config.seed + fold_index, history, f"fold{fold_index + 1}")
        fold_matrix = np.zeros((len(GROUPS), len(GROUPS)), dtype=np.int64)
        for i in validation.tolist():
            image, mask = items[i]
            predicted = predict_labels(model, image, config, device)
            matrix_classes += confusion_matrix(predicted, mask, NUM_CLASSES)
            grouped_pred, grouped_true = group_indices(predicted), group_indices(mask)
            fold_matrix += confusion_matrix(grouped_pred, grouped_true, len(GROUPS))
            per_image.append(
                {
                    "image": names[i],
                    "fold": fold_index + 1,
                    "true_necrotic_ratio": area_ratio(mask, NECROSIS_INDEX),
                    "predicted_necrotic_ratio": area_ratio(predicted, NECROSIS_INDEX),
                }
            )
        matrix_groups += fold_matrix
        fold_metrics = segmentation_metrics(fold_matrix, GROUPS)
        per_fold.append(
            {
                "fold": fold_index + 1,
                "validation_images": [names[i] for i in validation.tolist()],
                "mean_dice_foreground": fold_metrics["mean_dice_foreground"],
                "mean_iou_foreground": fold_metrics["mean_iou_foreground"],
            }
        )
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()

    return {
        "folds": len(per_fold),
        "classes": segmentation_metrics(matrix_classes, CLASS_KEYS),
        "groups": segmentation_metrics(matrix_groups, GROUPS),
        "necrotic_ratio_mae": float(
            np.mean([abs(r["true_necrotic_ratio"] - r["predicted_necrotic_ratio"]) for r in per_image])
        ),
        "per_fold": per_fold,
        "per_image": per_image,
    }


def dataset_summary(items, names) -> dict[str, Any]:
    pixels = np.zeros(NUM_CLASSES, dtype=np.int64)
    images_with = np.zeros(NUM_CLASSES, dtype=np.int64)
    for _, mask in items:
        counts = np.bincount(mask.ravel(), minlength=NUM_CLASSES)
        pixels += counts
        images_with += counts > 0
    return {
        "images": len(items),
        "names": names,
        "class_pixel_fraction": {k: float(p / pixels.sum()) for k, p in zip(CLASS_KEYS, pixels, strict=True)},
        "images_per_class": {k: int(n) for k, n in zip(CLASS_KEYS, images_with, strict=True)},
    }


def summary_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Resumen que se guarda en la tabla model_versions."""
    cv = metrics["cross_validation"]
    fold_dice = [f["mean_dice_foreground"] for f in cv["per_fold"] if f["mean_dice_foreground"] is not None]
    summary = {
        "evaluation": f"validación cruzada de {cv['folds']} particiones",
        "training_images": metrics["dataset"]["images"],
        # Media y desviación del Dice por partición: más honesta que la cifra agregada.
        "cv_fold_dice_mean": float(np.mean(fold_dice)) if fold_dice else None,
        "cv_fold_dice_std": float(np.std(fold_dice)) if fold_dice else None,
        # Dice agregado sobre la matriz de confusión de todas las particiones (dominado por las clases grandes).
        "cv_mean_dice_foreground": cv["groups"]["mean_dice_foreground"],
        "cv_mean_iou_foreground": cv["groups"]["mean_iou_foreground"],
        "cv_necrotic_dice": cv["groups"]["per_class"]["necrotic"]["dice"],
        "cv_necrotic_ratio_mae": cv["necrotic_ratio_mae"],
    }
    if "heuristic_baseline" in metrics:
        heuristic = metrics["heuristic_baseline"]
        summary["heuristic_mean_dice_foreground"] = heuristic["groups"]["mean_dice_foreground"]
        summary["heuristic_necrotic_dice"] = heuristic["groups"]["per_class"]["necrotic"]["dice"]
        summary["heuristic_necrotic_ratio_mae"] = heuristic["necrotic_ratio_mae"]
    return summary


def _fmt(value: Any) -> str:
    return "—" if value is None else f"{value:.3f}"


def write_model_card(path: Path, config: TrainConfig, metrics: dict[str, Any], run_id: str) -> None:
    cv, data = metrics["cross_validation"], metrics["dataset"]
    heuristic = metrics.get("heuristic_baseline")
    rows = []
    for group in GROUPS[1:]:
        model_dice = cv["groups"]["per_class"][group]["dice"]
        base_dice = heuristic["groups"]["per_class"][group]["dice"] if heuristic else None
        rows.append(f"| {group} | {_fmt(model_dice)} | {_fmt(base_dice)} |")
    encoder = "preentrenado en ImageNet" if config.pretrained_encoder else "sin preentrenar"
    lines = [
        f"# Ficha del modelo: {config.name} v{config.version}",
        "",
        "> Modelo **experimental** con fines educativos. No es una herramienta de diagnóstico médico.",
        "",
        f"- Ejecución: `{run_id}`",
        f"- Arquitectura: {ARCHITECTURE} (encoder {encoder})",
        f"- Datos: WoundTissue, muestra pública de {data['images']} imágenes (CC BY-NC-SA 4.0, uso no comercial)",
        "- Imágenes por clase: " + ", ".join(f"{k} {v}" for k, v in data["images_per_class"].items()),
        f"- Entrada: lado mayor {config.input_size} px · {config.epochs} épocas · semilla {config.seed}",
        "",
        "## Validación cruzada (Dice por grupo de tejido)",
        "",
        "| Grupo | Modelo | Heurística OpenCV |",
        "|---|---|---|",
        *rows,
        "",
        f"- Dice medio sin fondo por partición: {_fmt(metrics['summary']['cv_fold_dice_mean'])} "
        f"± {_fmt(metrics['summary']['cv_fold_dice_std'])} (de "
        + ", ".join(_fmt(f["mean_dice_foreground"]) for f in cv["per_fold"])
        + ")",
        "- Dice medio sin fondo agregado (todas las particiones juntas): "
        f"modelo {_fmt(cv['groups']['mean_dice_foreground'])}"
        + (f", heurística {_fmt(heuristic['groups']['mean_dice_foreground'])}" if heuristic else ""),
        f"- Error absoluto medio de la proporción necrótica: modelo {_fmt(cv['necrotic_ratio_mae'])}"
        + (f", heurística {_fmt(heuristic['necrotic_ratio_mae'])}" if heuristic else ""),
        "",
        "## Limitaciones",
        "",
        f"- Con {data['images']} imágenes, las métricas tienen una varianza enorme y no son representativas.",
        "- La necrosis aparece en muy pocas imágenes de la muestra; su segmentación no es fiable.",
        "- Las imágenes del dataset son recortes ajustados de heridas; "
        "fotos con mucha piel o fondo quedan fuera de su distribución.",
        "- La confianza que devuelve la inferencia no está calibrada.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_reports(run_dir: Path, config: TrainConfig, metrics: dict[str, Any]) -> None:
    """(Re)genera el resumen de métricas, `metrics.json` y `model_card.md` de una ejecución."""
    metrics["summary"] = summary_metrics(metrics)
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    write_model_card(run_dir / "model_card.md", config, metrics, run_dir.name)


def refresh_reports(run_dir: Path) -> None:
    """Recalcula los informes de una ejecución existente sin reentrenar (p. ej. tras añadir métricas)."""
    config = TrainConfig(**json.loads((run_dir / "config.json").read_text(encoding="utf-8")))
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    write_reports(run_dir, config, metrics)


def run(config: TrainConfig, output_dir: Path) -> Path:
    started = time.perf_counter()
    device = resolve_device(config.device)
    data_root = Path(config.data_root)
    if not data_root.is_absolute():
        data_root = PROJECT_ROOT / data_root
    samples = find_samples(data_root)
    items = [read_sample(s) for s in samples]
    names = [s.name for s in samples]

    run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{config.name}"
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "config.json").write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "environment.json").write_text(
        json.dumps(environment_info(device, samples), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[{run_id}] {len(items)} imágenes · dispositivo {device}", flush=True)

    history: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {"dataset": dataset_summary(items, names)}
    metrics["cross_validation"] = cross_validate(items, names, config, device, history)
    cv_dice = metrics["cross_validation"]["groups"]["mean_dice_foreground"]
    print(f"  validación cruzada: Dice medio sin fondo {_fmt(cv_dice)}", flush=True)
    if config.evaluate_heuristic:
        metrics["heuristic_baseline"] = evaluate_heuristic(items, names)

    final_model = train_model(items, config, device, config.seed, history, "final")
    meta = {
        "name": config.name,
        "version": config.version,
        "description": config.description,
        "architecture": ARCHITECTURE,
        "classes": CLASS_KEYS,
        "input_size": config.input_size,
        "normalization": "imagenet",
        "pretrained_encoder": config.pretrained_encoder,
        "training_images": len(items),
        "dataset": "WoundTissue (muestra pública, CC BY-NC-SA 4.0)",
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
    }
    save_checkpoint(run_dir / "model.pt", final_model, meta)
    (run_dir / "model_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    metrics["duration_seconds"] = round(time.perf_counter() - started, 1)
    with (run_dir / "history.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stage", "epoch", "loss", "cross_entropy", "dice"])
        writer.writeheader()
        writer.writerows(history)
    write_reports(run_dir, config, metrics)
    print(f"  listo en {metrics['duration_seconds']} s → {run_dir}", flush=True)
    return run_dir


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description="Entrena y evalúa el modelo de segmentación de tejidos.")
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--refresh-reports", type=Path, metavar="RUN_DIR", help="Regenerar informes de una ejecución sin reentrenar"
    )
    parser.add_argument("--data-root")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "ai" / "experiments" / "runs")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--folds", type=int)
    parser.add_argument("--samples-per-image", type=int)
    parser.add_argument("--device")
    parser.add_argument("--no-pretrained", action="store_true", help="No descargar ni usar pesos de ImageNet")
    args = parser.parse_args(argv)
    if args.refresh_reports:
        refresh_reports(args.refresh_reports)
        return args.refresh_reports
    if args.config is None:
        parser.error("--config es obligatorio para entrenar")

    overrides = {
        "data_root": args.data_root,
        "epochs": args.epochs,
        "folds": args.folds,
        "samples_per_image": args.samples_per_image,
        "device": args.device,
        "pretrained_encoder": False if args.no_pretrained else None,
    }
    return run(TrainConfig.load(args.config, overrides), args.output_dir)


if __name__ == "__main__":
    main()
