"""Métricas de segmentación por clase a partir de una matriz de confusión (NumPy, sin PyTorch)."""

from typing import Any

import numpy as np


def confusion_matrix(prediction: np.ndarray, target: np.ndarray, num_classes: int) -> np.ndarray:
    """Matriz (verdad × predicción) con el número de píxeles de cada combinación."""
    if prediction.shape != target.shape:
        raise ValueError("La predicción y la referencia deben tener el mismo tamaño.")
    index = target.astype(np.int64).ravel() * num_classes + prediction.astype(np.int64).ravel()
    return np.bincount(index, minlength=num_classes * num_classes).reshape(num_classes, num_classes)


def _ratio(numerator: float, denominator: float) -> float | None:
    return float(numerator / denominator) if denominator > 0 else None


def segmentation_metrics(matrix: np.ndarray, class_names: list[str] | tuple[str, ...]) -> dict[str, Any]:
    """IoU, Dice, precisión, sensibilidad y especificidad por clase, y sus medias.

    Las métricas de una clase son `None` si no están definidas (p. ej. clase ausente en la
    referencia y en la predicción). Las medias usan solo las clases presentes en la referencia;
    `mean_*_foreground` excluye además la primera clase (fondo).
    """
    total = matrix.sum()
    per_class: dict[str, dict[str, Any]] = {}
    for index, name in enumerate(class_names):
        tp = float(matrix[index, index])
        fp = float(matrix[:, index].sum() - tp)
        fn = float(matrix[index, :].sum() - tp)
        tn = float(total - tp - fp - fn)
        per_class[name] = {
            "support_pixels": int(tp + fn),
            "predicted_pixels": int(tp + fp),
            "iou": _ratio(tp, tp + fp + fn),
            "dice": _ratio(2 * tp, 2 * tp + fp + fn),
            "precision": _ratio(tp, tp + fp),
            "sensitivity": _ratio(tp, tp + fn),
            "specificity": _ratio(tn, tn + fp),
        }

    def mean(metric: str, skip_first: bool) -> float | None:
        names = list(class_names)[1:] if skip_first else list(class_names)
        values = [
            per_class[n][metric]
            for n in names
            if per_class[n]["support_pixels"] > 0 and per_class[n][metric] is not None
        ]
        return float(np.mean(values)) if values else None

    return {
        "pixel_accuracy": _ratio(float(np.trace(matrix)), float(total)),
        "mean_iou": mean("iou", skip_first=False),
        "mean_dice": mean("dice", skip_first=False),
        "mean_iou_foreground": mean("iou", skip_first=True),
        "mean_dice_foreground": mean("dice", skip_first=True),
        "per_class": per_class,
    }


def area_ratio(labels: np.ndarray, class_index: int, background_index: int = 0) -> float:
    """Proporción de la región no-fondo que pertenece a `class_index` (0 si no hay región)."""
    region = labels != background_index
    count = int(region.sum())
    return float((labels[region] == class_index).sum() / count) if count else 0.0
