"""Inferencia con un modelo entrenado y conversión al mismo formato de resultado que la heurística."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch

from ai.preprocessing import AnalysisOutput, PipelineConfig, decode_image, preprocess
from ai.preprocessing import features as feature_extraction
from ai.preprocessing.pipeline import _round, quality_warnings

from .classes import GROUPS, WOUNDTISSUE_CLASSES, TissueClass
from .transforms import normalize, resize_longest
from .unet import UNetResNet18

CONFIDENCE_DEFINITION = (
    "Media, sobre los píxeles de herida, de la probabilidad que el modelo asigna a la clase "
    "predicha. No está calibrada: no es la probabilidad de que el resultado sea correcto."
)
MIN_WOUND_RATIO = 0.002


@dataclass(frozen=True)
class LoadedModel:
    model: torch.nn.Module
    meta: dict[str, Any]
    device: torch.device

    @property
    def classes(self) -> tuple[TissueClass, ...]:
        keys = self.meta["classes"]
        by_key = {c.key: c for c in WOUNDTISSUE_CLASSES}
        return tuple(by_key[key] for key in keys)


def resolve_device(preference: str = "auto") -> torch.device:
    if preference == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(preference)


def save_checkpoint(path: Path, model: torch.nn.Module, meta: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "meta": meta}, path)


def load_model(path: str | Path, device: str = "auto") -> LoadedModel:
    """Carga un checkpoint de `save_checkpoint`. No descarga nada: el encoder se crea sin pesos."""
    checkpoint = torch.load(Path(path), map_location="cpu", weights_only=True)
    meta = checkpoint["meta"]
    model = UNetResNet18(num_classes=len(meta["classes"]), pretrained_encoder=False)
    model.load_state_dict(checkpoint["state_dict"])
    target = resolve_device(device)
    model.to(target).eval()
    return LoadedModel(model, meta, target)


@lru_cache(maxsize=4)
def _cached(path: str, mtime: float, device: str) -> LoadedModel:
    return load_model(path, device)


def load_model_cached(path: str | Path, device: str = "auto") -> LoadedModel:
    """Como `load_model`, pero reutiliza el modelo mientras el archivo no cambie."""
    resolved = Path(path).resolve()
    return _cached(str(resolved), resolved.stat().st_mtime, device)


@torch.inference_mode()
def predict_probabilities(loaded: LoadedModel, image_rgb: np.ndarray) -> np.ndarray:
    """Probabilidades por clase (C, H, W) al tamaño de `image_rgb`."""
    size = int(loaded.meta["input_size"])
    resized = resize_longest(image_rgb, size)
    tensor = torch.from_numpy(normalize(resized)).unsqueeze(0).to(loaded.device)
    probabilities = torch.softmax(loaded.model(tensor), dim=1)[0].float().cpu().numpy()
    height, width = image_rgb.shape[:2]
    return np.stack([cv2.resize(p, (width, height), interpolation=cv2.INTER_LINEAR) for p in probabilities])


def render_model_overlay(base_bgr: np.ndarray, labels: np.ndarray, classes: tuple[TissueClass, ...]) -> np.ndarray:
    output = base_bgr.astype(np.float32)
    for tissue_class in classes:
        if tissue_class.group == "background":
            continue
        mask = labels == tissue_class.index
        red, green, blue = tissue_class.display_color
        output[mask] = output[mask] * 0.5 + np.array([blue, green, red], np.float32) * 0.5
    output = output.astype(np.uint8)
    wound = (labels != 0).astype(np.uint8)
    contours, _ = cv2.findContours(wound, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(output, contours, -1, (80, 220, 80), 2, lineType=cv2.LINE_AA)
    return output


def _legend(classes: tuple[TissueClass, ...]) -> list[dict[str, str]]:
    items = [{"label": "Herida detectada", "color": "#50dc50", "kind": "outline"}]
    for c in classes:
        if c.group != "background":
            items.append({"label": c.label, "color": "#{:02x}{:02x}{:02x}".format(*c.display_color), "kind": "fill"})
    return items


def analyze_with_model(
    image_bgr: np.ndarray, loaded: LoadedModel, config: PipelineConfig | None = None
) -> AnalysisOutput:
    """Segmenta los tejidos con el modelo y devuelve el mismo formato que `ai.preprocessing.analyze_image`.

    - `necrotic_area_ratio`: píxeles de necrosis sobre los píxeles de herida (no fondo).
    - `result["confidence"]`: ver `CONFIDENCE_DEFINITION`.
    Las características de color, textura, bordes y forma se calculan sobre la herida detectada.
    """
    config = config or PipelineConfig()
    pre = preprocess(image_bgr, config)
    classes = loaded.classes
    rgb = cv2.cvtColor(pre.resized, cv2.COLOR_BGR2RGB)
    probabilities = predict_probabilities(loaded, rgb)
    labels = probabilities.argmax(axis=0)
    top_probability = probabilities.max(axis=0)

    wound = labels != 0
    wound_ratio = float(wound.mean())
    has_wound = wound_ratio >= MIN_WOUND_RATIO
    wound_pixels = int(wound.sum())

    class_composition = {
        c.key: (float((labels[wound] == c.index).sum() / wound_pixels) if wound_pixels else 0.0)
        for c in classes
        if c.group != "background"
    }
    tissue_composition = {"necrotic": 0.0, "slough": 0.0, "granulation": 0.0, "other": 0.0}
    for c in classes:
        if c.group != "background":
            tissue_composition[c.group] += class_composition[c.key]

    confidence = float(top_probability[wound].mean()) if has_wound else float(top_probability.mean())
    quality = feature_extraction.quality_features(pre.lab, pre.gray, pre.glare)
    warnings = quality_warnings(image_bgr.shape, quality)
    if not has_wound:
        warnings.insert(0, "El modelo no detectó tejido de herida en la imagen.")
    training_images = loaded.meta.get("training_images")
    if isinstance(training_images, int) and training_images < 100:
        warnings.append(
            f"Modelo de prueba de concepto entrenado con solo {training_images} imágenes; "
            "sus resultados no son fiables."
        )

    region = wound & ~pre.glare if has_wound else np.zeros_like(wound)
    if has_wound and not region.any():
        region = wound
    skin_mask = ~wound & ~pre.glare
    skin_lab = np.median(pre.lab[skin_mask], axis=0) if skin_mask.any() else np.median(pre.lab.reshape(-1, 3), axis=0)
    skin_tuple = (float(skin_lab[0]), float(skin_lab[1]), float(skin_lab[2]))

    result = {
        "method": {
            "name": loaded.meta["name"],
            "version": loaded.meta["version"],
            "type": "model",
            "description": loaded.meta.get("description", ""),
        },
        "model": {
            "architecture": loaded.meta.get("architecture"),
            "classes": list(loaded.meta["classes"]),
            "input_size": loaded.meta["input_size"],
            "training_images": training_images,
            "device": str(loaded.device),
        },
        "confidence_definition": CONFIDENCE_DEFINITION,
        "segmentation": {"roi_area_ratio": wound_ratio, "fallback_full_image": False},
        "tissue_composition": tissue_composition,
        "class_composition": class_composition,
        "color": feature_extraction.color_features(pre.lab, region, skin_tuple) if has_wound else None,
        "texture": feature_extraction.texture_features(pre.gray, region, config.glcm_levels) if has_wound else None,
        "edges": feature_extraction.edge_features(pre.gray, region, roi_is_lesion=True) if has_wound else None,
        "shape": feature_extraction.shape_features(wound) if has_wound else None,
        "quality": quality,
        "warnings": warnings,
        "legend": _legend(classes),
    }

    return AnalysisOutput(
        necrotic_area_ratio=round(tissue_composition["necrotic"], 4),
        result=_round(result),
        overlay=render_model_overlay(pre.resized, labels, classes),
        roi_mask=wound,
        tissue_labels=labels.astype(np.uint8),
        confidence=round(confidence, 4),
    )


def analyze_bytes_with_model(data: bytes, loaded: LoadedModel) -> AnalysisOutput:
    return analyze_with_model(decode_image(data), loaded)


__all__ = [
    "CONFIDENCE_DEFINITION",
    "GROUPS",
    "LoadedModel",
    "analyze_bytes_with_model",
    "analyze_with_model",
    "load_model",
    "load_model_cached",
    "predict_probabilities",
    "resolve_device",
    "save_checkpoint",
]
