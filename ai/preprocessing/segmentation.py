"""Detección de reflejos y segmentación de la región de interés (lesión frente a piel)."""

from dataclasses import dataclass

import cv2
import numpy as np

from .config import PipelineConfig


@dataclass(frozen=True)
class Segmentation:
    mask: np.ndarray  # bool (H, W): región de interés
    skin_reference_lab: tuple[float, float, float]
    threshold_delta_e: float | None
    fallback: bool  # True si no se distinguió una lesión y se usa la imagen completa
    border_contact: float  # fracción de la franja del borde que cae dentro de la región


def detect_glare(image: np.ndarray, config: PipelineConfig) -> np.ndarray:
    """Reflejos especulares: píxeles casi blancos y sin saturación."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return (hsv[..., 2] >= config.glare_min_value) & (hsv[..., 1] <= config.glare_max_saturation)


def border_mask(shape: tuple[int, int], fraction: float) -> np.ndarray:
    height, width = shape
    margin = max(1, round(min(height, width) * fraction))
    mask = np.zeros((height, width), dtype=bool)
    mask[:margin, :] = True
    mask[-margin:, :] = True
    mask[:, :margin] = True
    mask[:, -margin:] = True
    return mask


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Rellena los huecos interiores de una máscara binaria."""
    padded = np.pad(mask.astype(np.uint8), 1)
    flood_mask = np.zeros((padded.shape[0] + 2, padded.shape[1] + 2), dtype=np.uint8)
    cv2.floodFill(padded, flood_mask, (0, 0), 1)
    holes = padded[1:-1, 1:-1] == 0
    return mask | holes


def _odd(value: float, minimum: int) -> int:
    size = max(minimum, round(value))
    return size if size % 2 == 1 else size + 1


def color_distance(lab: np.ndarray, reference: np.ndarray, lightness_weight: float = 0.5) -> np.ndarray:
    """Distancia de color ΔE (CIE76) con menos peso en L* para tolerar sombras suaves."""
    diff = lab - reference
    return np.sqrt((lightness_weight * diff[..., 0]) ** 2 + diff[..., 1] ** 2 + diff[..., 2] ** 2)


def segment_lesion(lab: np.ndarray, valid: np.ndarray, config: PipelineConfig) -> Segmentation:
    """Separa la lesión de la piel circundante por diferencia de color.

    1. La piel de referencia es la mediana Lab de una franja junto al borde (se asume la
       lesión aproximadamente centrada y rodeada de piel).
    2. Se calcula la distancia de color de cada píxel a esa referencia y se umbraliza con Otsu.
    3. Apertura y cierre morfológicos, componente conexa más grande y cercana al centro,
       y relleno de huecos.
    Si no se encuentra una región razonable se devuelve la imagen completa (`fallback`).
    """
    height, width = lab.shape[:2]
    border = border_mask((height, width), config.border_fraction)
    reference_pixels = lab[border & valid]
    if reference_pixels.size == 0:
        reference_pixels = lab[border]
    skin = np.median(reference_pixels, axis=0)
    skin_tuple = (float(skin[0]), float(skin[1]), float(skin[2]))

    def fallback() -> Segmentation:
        full = np.ones((height, width), dtype=bool)
        return Segmentation(full, skin_tuple, None, True, 1.0)

    distance = color_distance(lab, skin).astype(np.float32)
    distance = cv2.GaussianBlur(distance, (0, 0), max(1.0, 0.01 * max(height, width)))
    max_distance = float(distance.max())
    if max_distance < config.min_lesion_delta_e:
        return fallback()

    scaled = np.clip(distance / max_distance * 255.0, 0, 255).astype(np.uint8)
    otsu, _ = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    threshold = max(otsu / 255.0 * max_distance, config.min_lesion_delta_e)
    mask = ((distance > threshold) & valid).astype(np.uint8)

    longest = max(height, width)
    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_odd(0.01 * longest, 3),) * 2)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_odd(0.03 * longest, 5),) * 2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)

    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return fallback()

    center = np.array([width / 2.0, height / 2.0])
    best_label, best_score = 0, -1.0
    for label in range(1, count):
        offset = (centroids[label] - center) / center
        centrality = 1.0 - 0.5 * min(1.0, float(np.hypot(*offset)) / np.sqrt(2.0))
        score = float(stats[label, cv2.CC_STAT_AREA]) * centrality
        if score > best_score:
            best_label, best_score = label, score

    roi = fill_holes(labels == best_label)
    ratio = float(roi.mean())
    if not config.min_roi_ratio <= ratio <= config.max_roi_ratio:
        return fallback()

    contact = float((roi & border).sum() / border.sum())
    return Segmentation(roi, skin_tuple, float(threshold), False, contact)
