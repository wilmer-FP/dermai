"""Clasificación heurística de los píxeles de la lesión por color (negro / amarillo / rojo)."""

from dataclasses import dataclass

import cv2
import numpy as np

from .config import TissueThresholds

EXCLUDED = 0
NECROTIC = 1
SLOUGH = 2
GRANULATION = 3
OTHER = 4

TISSUE_NAMES: dict[int, str] = {
    NECROTIC: "necrotic",
    SLOUGH: "slough",
    GRANULATION: "granulation",
    OTHER: "other",
}


@dataclass(frozen=True)
class TissueMap:
    labels: np.ndarray  # uint8 (H, W) con los códigos de arriba; 0 fuera de la región
    ratios: dict[str, float]  # proporción de cada clase sobre los píxeles válidos de la región
    pixel_count: int


def _in_range(values: np.ndarray, bounds: tuple[float, float]) -> np.ndarray:
    return (values >= bounds[0]) & (values <= bounds[1])


def classify_tissue(
    lab: np.ndarray,
    region: np.ndarray,
    skin_lab: tuple[float, float, float],
    thresholds: TissueThresholds,
) -> TissueMap:
    """Asigna a cada píxel de `region` una clase de tejido según su color en CIELAB.

    Los umbrales combinan valores absolutos y diferencias respecto a la piel de referencia.
    Las estructuras oscuras muy finas (p. ej. vello) se eliminan de la clase necrótica
    con una apertura morfológica.
    """
    lightness, a_star, b_star = lab[..., 0], lab[..., 1], lab[..., 2]
    chroma = np.hypot(a_star, b_star)
    hue = np.degrees(np.arctan2(b_star, a_star))
    skin_l, skin_a, skin_b = skin_lab
    t = thresholds

    dark_limit = min(t.necrotic_max_lightness, skin_l - t.necrotic_min_darkening)
    necrotic = region & (lightness < dark_limit) & (chroma < t.necrotic_max_chroma)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    necrotic = cv2.morphologyEx(necrotic.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)

    slough = (
        region
        & ~necrotic
        & (lightness >= t.slough_min_lightness)
        & _in_range(hue, t.slough_hue_range)
        & (b_star >= max(t.slough_min_b, skin_b + t.slough_min_b_over_skin))
    )
    granulation = (
        region
        & ~necrotic
        & ~slough
        & _in_range(hue, t.granulation_hue_range)
        & (a_star >= max(t.granulation_min_a, skin_a + t.granulation_min_a_over_skin))
    )
    other = region & ~necrotic & ~slough & ~granulation

    labels = np.zeros(region.shape, dtype=np.uint8)
    labels[necrotic] = NECROTIC
    labels[slough] = SLOUGH
    labels[granulation] = GRANULATION
    labels[other] = OTHER

    total = int(region.sum())
    ratios = {
        name: (float((labels == code).sum()) / total if total else 0.0)
        for code, name in TISSUE_NAMES.items()
    }
    return TissueMap(labels, ratios, total)
